#!/usr/bin/env python3


import pytest
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pose_engine.model_instance import ModelInstance
from pose_engine.skeleton import Skeleton
from pose_engine.bone import Bone
from pose_engine.vec3 import Vec3
from pose_engine.quat import Quat
from pose_engine.transform import Transform


@pytest.fixture
def model_instance():
    
    return ModelInstance(name="TestModel")


@pytest.fixture
def model_with_skeleton(sample_skeleton):
    
    model = ModelInstance(name="SkeletonModel")
    model.skeleton = sample_skeleton
    return model


@pytest.fixture
def parent_model(sample_skeleton):
    
    model = ModelInstance(name="ParentModel")
    model.skeleton = sample_skeleton
    model.set_position(0, 0, 0)
    return model


@pytest.fixture
def child_model():
    
    model = ModelInstance(name="ChildModel")
    model.set_position(1, 0, 0)
    return model


@pytest.fixture
def test_glb_path():
    
    test_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "krita_3d_pose", "TEST.glb"
    )
    if os.path.exists(test_file):
        return test_file
    return None


class TestModelInstanceCreation:
    

    def test_model_instance_creation(self):
        
        model = ModelInstance(name="TestModel")

        assert model.name == "TestModel"
        assert model.skeleton is None
        assert model.mesh_data is None
        assert model.visible is True
        assert model.source_file is None

    def test_model_id_generation(self):
        
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")

        assert model1.id is not None
        assert model2.id is not None
        assert model1.id != model2.id
        assert len(model1.id) == 8

    def test_model_custom_id(self):
        
        model = ModelInstance(id="custom_id_123", name="CustomModel")

        assert model.id == "custom_id_123"
        assert model.name == "CustomModel"

    def test_model_default_transform(self):
        
        model = ModelInstance(name="TestModel")

        assert model.transform.position.x == 0
        assert model.transform.position.y == 0
        assert model.transform.position.z == 0

    def test_model_repr(self):
        
        model = ModelInstance(name="TestModel")

        repr_str = repr(model)
        assert "TestModel" in repr_str
        assert model.id in repr_str


class TestModelTransform:
    

    def test_model_transform(self):
        
        model = ModelInstance(name="TestModel")
    
        assert model.transform.position.x == 0
        assert model.transform.position.y == 0
        assert model.transform.position.z == 0

    def test_set_position(self):
        
        model = ModelInstance(name="TestModel")
        model.set_position(1.0, 2.0, 3.0)

        assert (model.transform.position.x - 1.0) < 0.01
        assert (model.transform.position.y - 2.0) < 0.01
        assert (model.transform.position.z - 3.0) < 0.01

    def test_translate(self):
        
        model = ModelInstance(name="TestModel")
        model.set_position(1.0, 2.0, 3.0)

        model.translate(Vec3(0.5, 0.5, 0.5))

        assert (model.transform.position.x - 1.5) < 0.01
        assert (model.transform.position.y - 2.5) < 0.01
        assert (model.transform.position.z - 3.5) < 0.01

    def test_rotate_y(self):
        
        model = ModelInstance(name="TestModel")
    
        model.rotate_y(90.0)
    
        assert (abs(model.transform.rotation.w - 1.0) > 0.001) or (abs(model.transform.rotation.x - 0.0) > 0.001)

    def test_get_world_position_no_parent(self):
        
        model = ModelInstance(name="TestModel")
        model.set_position(5.0, 10.0, 15.0)

        world_pos = model.get_world_position()

        assert (world_pos.x - 5.0) < 0.01
        assert (world_pos.y - 10.0) < 0.01
        assert (world_pos.z - 15.0) < 0.01

    def test_get_world_transform_no_parent(self):
        
        model = ModelInstance(name="TestModel")
        model.set_position(1.0, 2.0, 3.0)

        world_transform = model.get_world_transform()

        assert (world_transform.position.x - 1.0) < 0.01
        assert (world_transform.position.y - 2.0) < 0.01
        assert (world_transform.position.z - 3.0) < 0.01


class TestModelVisibility:
    

    def test_model_visibility_default(self):
        
        model = ModelInstance(name="TestModel")

        assert model.visible is True

    def test_model_visibility_toggle(self):
        
        model = ModelInstance(name="TestModel")

        model.visible = False
        assert model.visible is False

        model.visible = True
        assert model.visible is True


class TestModelParentChild:
    

    def test_model_parent_child(self):
        
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
    
        assert child.get_parent() is None
        assert len(parent.get_children()) == 0
    
        child.set_parent(parent)

        assert child.get_parent() is parent
        assert child in parent.get_children()

    def test_set_parent(self):
        
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")

        child.set_parent(parent)

        assert child.get_parent() is parent
        assert len(parent.get_children()) == 1
        assert parent.get_children()[0] is child

    def test_set_parent_none(self):
        
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
    
        child.set_parent(parent)
        assert child.get_parent() is parent
    
        child.set_parent(None)
        assert child.get_parent() is None
        assert child not in parent.get_children()

    def test_reparenting(self):
        
        parent1 = ModelInstance(name="Parent1")
        parent2 = ModelInstance(name="Parent2")
        child = ModelInstance(name="Child")
    
        child.set_parent(parent1)
        assert child.get_parent() is parent1
        assert child in parent1.get_children()
    
        child.set_parent(parent2)
        assert child.get_parent() is parent2
        assert child not in parent1.get_children()
        assert child in parent2.get_children()

    def test_get_children_copy(self):
        
        parent = ModelInstance(name="Parent")
        child1 = ModelInstance(name="Child1")
        child2 = ModelInstance(name="Child2")

        child1.set_parent(parent)
        child2.set_parent(parent)

        children = parent.get_children()
        assert len(children) == 2
    
        children.clear()
        assert len(parent.get_children()) == 2

    def test_get_world_position_with_parent(self):
        
        parent = ModelInstance(name="Parent")
        parent.set_position(10.0, 0.0, 0.0)

        child = ModelInstance(name="Child")
        child.set_position(5.0, 0.0, 0.0)
        child.set_parent(parent)

        world_pos = child.get_world_position()
    
        assert (world_pos.x - 15.0) < 0.01

    def test_nested_hierarchy(self):
        
        grandparent = ModelInstance(name="Grandparent")
        grandparent.set_position(0.0, 0.0, 0.0)

        parent = ModelInstance(name="Parent")
        parent.set_position(10.0, 0.0, 0.0)
        parent.set_parent(grandparent)

        child = ModelInstance(name="Child")
        child.set_position(5.0, 0.0, 0.0)
        child.set_parent(parent)
    
        world_pos = child.get_world_position()
        assert (world_pos.x - 15.0) < 0.01


class TestBoneAttachment:
    

    def test_attach_to_bone(self):
        
        parent = ModelInstance(name="Parent")
        parent.skeleton = Skeleton()

        bone = parent.skeleton.add_bone("attach_bone", parent_index=-1)
        bone.bind_transform.set_position(2.0, 0.0, 0.0)
        parent.skeleton.update_all_transforms()

        child = ModelInstance(name="Child")
        child.set_position(1.0, 0.0, 0.0)
        child.set_parent(parent, bone_name="attach_bone")

        assert child.get_parent() is parent
        assert child.get_parent_bone() == "attach_bone"

    def test_get_parent_bone(self):
        
        parent = ModelInstance(name="Parent")
        parent.skeleton = Skeleton()
        parent.skeleton.add_bone("test_bone", parent_index=-1)

        child = ModelInstance(name="Child")
        child.set_parent(parent, bone_name="test_bone")

        assert child.get_parent_bone() == "test_bone"

    def test_get_parent_bone_none(self):
        
        parent = ModelInstance(name="Parent")
        child = ModelInstance(name="Child")
        child.set_parent(parent)

        assert child.get_parent_bone() is None


class TestSkeletonAccess:
    

    def test_get_bone_count_empty(self):
        
        model = ModelInstance(name="TestModel")

        assert model.get_bone_count() == 0

    def test_get_bone_count_with_skeleton(self, sample_skeleton):
        
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton
    
        assert model.get_bone_count() == 5

    def test_get_bone(self, sample_skeleton):
        
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        bone = model.get_bone("root")
        assert bone is not None
        assert bone.name == "root"

    def test_get_bone_not_found(self, sample_skeleton):
        
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        bone = model.get_bone("nonexistent")
        assert bone is None

    def test_get_bone_no_skeleton(self):
        
        model = ModelInstance(name="TestModel")

        bone = model.get_bone("any_bone")
        assert bone is None

    def test_get_root_bones(self, sample_skeleton):
        
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton

        roots = model.get_root_bones()
        assert len(roots) == 1
        assert roots[0].name == "root"

    def test_get_root_bones_no_skeleton(self):
        
        model = ModelInstance(name="TestModel")

        roots = model.get_root_bones()
        assert roots == []

    def test_update_transforms(self, sample_skeleton):
        
        model = ModelInstance(name="TestModel")
        model.skeleton = sample_skeleton
    
        model.update_transforms()


class TestModelCopying:
    

    def test_copy_creates_new_instance(self, sample_skeleton):
        
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton
        model.set_position(1.0, 2.0, 3.0)

        copy = model.copy()

        assert copy is not model
        assert copy.id != model.id
        assert copy.name == "Original (copy)"

    def test_copy_skeleton_deep(self, sample_skeleton):
        
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton

        copy = model.copy()
    
        assert copy.skeleton is not model.skeleton
    
        assert len(copy.skeleton) == len(model.skeleton)

    def test_copy_preserves_pose(self, sample_skeleton):
        
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton
    
        bone = model.skeleton.get_bone("root")
        bone.pose_transform.rotation = Quat(0.707, 0.0, 0.707, 0.0)

        copy = model.copy()
    
        copy_bone = copy.skeleton.get_bone("root")
        assert abs(copy_bone.pose_transform.rotation.w - 0.707) < 0.001

    def test_copy_custom_name(self, sample_skeleton):
        
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton

        copy = model.copy(name="CustomCopy")

        assert copy.name == "CustomCopy"

    def test_copy_transform(self, sample_skeleton):
        
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton
        model.set_position(5.0, 10.0, 15.0)

        copy = model.copy()

        assert (copy.transform.position.x -  5.0) < 0.01
        assert (copy.transform.position.y - 10.0) < 0.01
        assert (copy.transform.position.z - 15.0) < 0.01

    def test_copy_mesh_data_shared(self, sample_skeleton):
        
        model = ModelInstance(name="Original")
        model.skeleton = sample_skeleton
    
        copy = model.copy()
    
        assert copy.mesh_data is model.mesh_data


@pytest.mark.integration
class TestGLBLoading:
    

    def test_load_from_glb(self, test_glb_path):
        
        if test_glb_path is None:
            pytest.skip("No test GLB file available")

        model = ModelInstance(name="GLBModel")
        model.load_from_glb(test_glb_path)
    
        assert model.skeleton is not None
        assert model.get_bone_count() > 0
    
        assert model.source_file == test_glb_path

    def test_load_from_glb_skeleton_valid(self, test_glb_path):
        
        if test_glb_path is None:
            pytest.skip("No test GLB file available")

        model = ModelInstance(name="GLBModel")
        model.load_from_glb(test_glb_path)
    
        for bone in model.skeleton:
            pos = bone.get_world_position()
            assert isinstance(pos.x, float)
            assert isinstance(pos.y, float)
            assert isinstance(pos.z, float)

    def test_load_from_glb_mesh_data(self, test_glb_path):
        
        if test_glb_path is None:
            pytest.skip("No test GLB file available")

        model = ModelInstance(name="GLBModel")
        model.load_from_glb(test_glb_path)
    
        assert model.mesh_data is not None


class TestGPUResources:
    

    def test_initialize_gl(self):
        
        model = ModelInstance(name="TestModel")
    
        assert model._gl_initialized is False
    
        result = model.initialize_gl()
        assert result is True
        assert model._gl_initialized is True

    def test_initialize_gl_idempotent(self):
        
        model = ModelInstance(name="TestModel")

        model.initialize_gl()
        model.initialize_gl()

        assert model._gl_initialized is True

    def test_cleanup_gl(self):
        
        model = ModelInstance(name="TestModel")

        model.initialize_gl()
        assert model._gl_initialized is True

        model.cleanup_gl()
        assert model._gl_initialized is False


class TestEdgeCases:
    

    def test_empty_name(self):
        
        model = ModelInstance(name="")
        assert model.name == ""

    def test_special_characters_in_name(self):
        
        model = ModelInstance(name="Test-Model_123!@#")
        assert model.name == "Test-Model_123!@#"

    def test_very_long_name(self):
        
        long_name = "A" * 1000
        model = ModelInstance(name=long_name)
        assert model.name == long_name

    def test_circular_parent_prevention(self):
        
        model1 = ModelInstance(name="Model1")
        model2 = ModelInstance(name="Model2")
    
        model2.set_parent(model1)
    
        model1.set_parent(model2)

        
        assert model1.get_parent() is model2
        assert model2.get_parent() is model1

    def test_self_parenting(self):
        
        model = ModelInstance(name="SelfParent")
    
        model.set_parent(model)
    
        
        assert model.get_parent() is model

    def test_multiple_children(self):
        
        parent = ModelInstance(name="Parent")
    
        children = []
        for i in range(100):
            child = ModelInstance(name=f"Child{i}")
            child.set_parent(parent)
            children.append(child)

        assert len(parent.get_children()) == 100
    
        for child in children:
            assert child in parent.get_children()


class TestWorldTransformHierarchy:
    

    def test_world_transform_deep_hierarchy(self):
        
        models = []
        for i in range(5):
            model = ModelInstance(name=f"Model{i}")
            model.set_position(1.0, 0.0, 0.0)
            if i > 0:
                model.set_parent(models[i - 1])
            models.append(model)

        world_pos = models[4].get_world_position()
        assert abs(world_pos.x - 5.0) < 0.001

    def test_world_transform_with_rotation(self):
        
        parent = ModelInstance(name="Parent")
        parent.set_position(0.0, 0.0, 0.0)

        child = ModelInstance(name="Child")
        child.set_position(1.0, 0.0, 0.0)
        child.set_parent(parent)
    
        parent.rotate_y(90.0)
    
        
        world_pos = child.get_world_position()
    
        assert abs(world_pos.x - 0.0) < 0.001
        assert abs(world_pos.y - 0.0) < 0.001
        assert abs(world_pos.z - (-1.0)) < 0.001

    def test_world_transform_with_scale(self):
        
        parent = ModelInstance(name="Parent")
        parent.set_position(0.0, 0.0, 0.0)
        parent.transform.scale = Vec3(2.0, 2.0, 2.0)

        child = ModelInstance(name="Child")
        child.set_position(1.0, 1.0, 1.0)
        child.set_parent(parent)
    
        world_pos = child.get_world_position()
    
        
        assert abs(world_pos.x - 2.0) < 0.001
        assert abs(world_pos.y - 2.0) < 0.001
        assert abs(world_pos.z - 2.0) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
