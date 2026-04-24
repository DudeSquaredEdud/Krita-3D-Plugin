from typing import List, Tuple
from .vec3 import Vec3
from .mat4 import Mat4
from .quat import Quat


class DualQuat:
    
    __slots__ = ('real', 'dual')
    
    def __init__(self, real: Quat = None, dual: Quat = None):
        self.real = real if real is not None else Quat(1, 0, 0, 0)
        self.dual = dual if dual is not None else Quat(0, 0, 0, 0)
    
    @classmethod
    def from_matrix(cls, mat: Mat4) -> 'DualQuat':
        real = Quat.from_matrix(mat)
        real = real.normalized()
        
        tx = mat.m[12]
        ty = mat.m[13]
        tz = mat.m[14]
        
        t_quat = Quat(0, tx, ty, tz)
        dual = t_quat * real
        dual = Quat(dual.w * 0.5, dual.x * 0.5, dual.y * 0.5, dual.z * 0.5)
        
        return cls(real, dual)
    
    def normalized(self) -> 'DualQuat':
        norm = self.real.length()
        if norm < 1e-10:
            return DualQuat(Quat(1, 0, 0, 0), Quat(0, 0, 0, 0))
        return DualQuat(
            Quat(self.real.w / norm, self.real.x / norm, 
                 self.real.y / norm, self.real.z / norm),
            Quat(self.dual.w / norm, self.dual.x / norm,
                 self.dual.y / norm, self.dual.z / norm)
        )
    
    def __add__(self, other: 'DualQuat') -> 'DualQuat':
        return DualQuat(
            Quat(self.real.w + other.real.w,
                 self.real.x + other.real.x,
                 self.real.y + other.real.y,
                 self.real.z + other.real.z),
            Quat(self.dual.w + other.dual.w,
                 self.dual.x + other.dual.x,
                 self.dual.y + other.dual.y,
                 self.dual.z + other.dual.z)
        )
    
    def __mul__(self, scalar: float) -> 'DualQuat':
        return DualQuat(
            Quat(self.real.w * scalar, self.real.x * scalar,
                 self.real.y * scalar, self.real.z * scalar),
            Quat(self.dual.w * scalar, self.dual.x * scalar,
                 self.dual.y * scalar, self.dual.z * scalar)
        )
    
    def transform_point(self, p: Vec3) -> Vec3:
        n = self.normalized()
        
        # Extract translation from dual quaternion
        # translation = 2 * (q_dual * q_real.conjugate()).xyz
        # where conjugate flips x, y, z but not w
        conj = Quat(n.real.w, -n.real.x, -n.real.y, -n.real.z)
        t_quat = n.dual * conj
        t_quat = Quat(t_quat.w * 2, t_quat.x * 2, t_quat.y * 2, t_quat.z * 2)
        translation = Vec3(t_quat.x, t_quat.y, t_quat.z)
        
        rotated = n.real.rotate_vector(p)
        
        return rotated + translation
    
    def transform_vector(self, v: Vec3) -> Vec3:
        n = self.normalized()
        return n.real.rotate_vector(v)


class VertexSkinning:
    __slots__ = ('bone_indices', 'weights', 'max_influences')

    def __init__(self, max_influences: int = 4):
        self.bone_indices: List[int] = []
        self.weights: List[float] = []
        self.max_influences = max_influences

    def add_influence(self, bone_index: int, weight: float) -> None:
        if len(self.bone_indices) >= self.max_influences:
            min_idx = 0
            min_weight = self.weights[0]
            for i, w in enumerate(self.weights):
                if w < min_weight:
                    min_idx = i
                    min_weight = w
            if weight > min_weight:
                self.bone_indices[min_idx] = bone_index
                self.weights[min_idx] = weight
        else:
            self.bone_indices.append(bone_index)
            self.weights.append(weight)

    def normalize_weights(self) -> None:
        total = sum(self.weights)
        if total > 0.0001:
            self.weights = [w / total for w in self.weights]
        elif len(self.weights) > 0:
            equal = 1.0 / len(self.weights)
            self.weights = [equal] * len(self.weights)

    def get_influences(self) -> List[Tuple[int, float]]:
        return list(zip(self.bone_indices, self.weights))

    def __repr__(self) -> str:
        pairs = [f"({idx}:{w:.3f})" for idx, w in zip(self.bone_indices, self.weights)]
        return f"VertexSkinning([{', '.join(pairs)}])"


class SkinningData:
    def __init__(self, vertex_count: int = 0):
        self._vertex_skinning: List[VertexSkinning] = [
            VertexSkinning() for _ in range(vertex_count)
        ]
        self._bone_matrices: List[Mat4] = []
        self._bone_dual_quats: List[DualQuat] = []

    def set_vertex_count(self, count: int) -> None:
        self._vertex_skinning = [
            VertexSkinning() for _ in range(count)
        ]

    def get_vertex_count(self) -> int:
        return len(self._vertex_skinning)

    def get_vertex_skinning(self, vertex_index: int) -> VertexSkinning:
        return self._vertex_skinning[vertex_index]

    def set_bone_matrices(self, matrices: List[Mat4]) -> None:
        self._bone_matrices = matrices
        # Pre-compute dual quaternions for DQS
        self._bone_dual_quats = [DualQuat.from_matrix(m) for m in matrices]

    def get_bone_matrices(self) -> List[Mat4]:
        return self._bone_matrices

    def get_bone_dual_quats(self) -> List[DualQuat]:
        return self._bone_dual_quats

    def skin_position_lbs(self, vertex_index: int, position: Vec3) -> Vec3:
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return position

        result = Vec3(0, 0, 0)

        for bone_idx, weight in zip(skinning.bone_indices, skinning.weights):
            if bone_idx < len(self._bone_matrices):
                matrix = self._bone_matrices[bone_idx]
                transformed = matrix.transform_point(position)
                result = result + transformed * weight

        return result

    def skin_position_dqs(self, vertex_index: int, position: Vec3) -> Vec3:
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return position

        blended = DualQuat()

        for i, (bone_idx, weight) in enumerate(zip(skinning.bone_indices, skinning.weights)):
            if bone_idx < len(self._bone_dual_quats):
                dq = self._bone_dual_quats[bone_idx]

                if i != 0:
                    dot = (self._bone_dual_quats[skinning.bone_indices[0]].real.w * dq.real.w +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.x * dq.real.x +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.y * dq.real.y +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.z * dq.real.z)
                    if dot < 0:
                        dq = DualQuat(
                            Quat(-dq.real.w, -dq.real.x, -dq.real.y, -dq.real.z),
                            Quat(-dq.dual.w, -dq.dual.x, -dq.dual.y, -dq.dual.z)
                        )
                
                blended = blended + dq * weight

        return blended.normalized().transform_point(position)

    def skin_position(self, vertex_index: int, position: Vec3, use_dqs: bool = True) -> Vec3:
        if use_dqs:
            return self.skin_position_dqs(vertex_index, position)
        else:
            return self.skin_position_lbs(vertex_index, position)

    def skin_normal_lbs(self, vertex_index: int, normal: Vec3) -> Vec3:
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return normal

        result = Vec3(0, 0, 0)

        for bone_idx, weight in zip(skinning.bone_indices, skinning.weights):
            if bone_idx < len(self._bone_matrices):
                matrix = self._bone_matrices[bone_idx]
                transformed = matrix.transform_vector(normal)
                result = result + transformed * weight

        return result

    def skin_normal_dqs(self, vertex_index: int, normal: Vec3) -> Vec3:
        skinning = self._vertex_skinning[vertex_index]

        if len(skinning.bone_indices) == 0:
            return normal

        blended = DualQuat()

        for i, (bone_idx, weight) in enumerate(zip(skinning.bone_indices, skinning.weights)):
            if bone_idx < len(self._bone_dual_quats):
                dq = self._bone_dual_quats[bone_idx]
                
                if i > 0:
                    dot = (self._bone_dual_quats[skinning.bone_indices[0]].real.w * dq.real.w +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.x * dq.real.x +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.y * dq.real.y +
                           self._bone_dual_quats[skinning.bone_indices[0]].real.z * dq.real.z)
                    if dot < 0:
                        dq = DualQuat(
                            Quat(-dq.real.w, -dq.real.x, -dq.real.y, -dq.real.z),
                            Quat(-dq.dual.w, -dq.dual.x, -dq.dual.y, -dq.dual.z)
                        )
                
                blended = blended + dq * weight

        return blended.normalized().transform_vector(normal)

    def skin_normal(self, vertex_index: int, normal: Vec3, use_dqs: bool = True) -> Vec3:
        if use_dqs:
            return self.skin_normal_dqs(vertex_index, normal)
        else:
            return self.skin_normal_lbs(vertex_index, normal)


def apply_skinning(
    positions: List[Vec3],
    normals: List[Vec3],
    skinning_data: SkinningData,
    use_dqs: bool = True
) -> Tuple[List[Vec3], List[Vec3]]:
    skinned_positions: List[Vec3] = []
    skinned_normals: List[Vec3] = []

    for i, pos in enumerate(positions):
        skinned_pos = skinning_data.skin_position(i, pos, use_dqs=use_dqs)
        skinned_positions.append(skinned_pos)

        if i < len(normals):
            skinned_nrm = skinning_data.skin_normal(i, normals[i], use_dqs=use_dqs)
            skinned_nrm = skinned_nrm.normalized()
            skinned_normals.append(skinned_nrm)

    return skinned_positions, skinned_normals


def compute_bone_matrices_from_skeleton(skeleton, skinning_data: SkinningData) -> None:
    matrices: List[Mat4] = []

    for bone in skeleton:
        matrices.append(bone.get_final_matrix())

    skinning_data.set_bone_matrices(matrices)
