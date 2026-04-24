import math
from typing import Tuple


class Vec3:
    
    __slots__ = ('x', 'y', 'z')
    
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
    
    def __repr__(self) -> str:
        return f"Vec3({self.x:.4f}, {self.y:.4f}, {self.z:.4f})"
    
    def __add__(self, other: 'Vec3') -> 'Vec3':
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other: 'Vec3') -> 'Vec3':
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar: float) -> 'Vec3':
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def __rmul__(self, scalar: float) -> 'Vec3':
        return self.__mul__(scalar)
    
    def __truediv__(self, scalar: float) -> 'Vec3':
        if abs(scalar) < 1e-10:
            return Vec3(0, 0, 0)
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)
    
    def __neg__(self) -> 'Vec3':
        return Vec3(-self.x, -self.y, -self.z)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vec3):
            return False
        return (abs(self.x - other.x) < 1e-10 and 
                abs(self.y - other.y) < 1e-10 and 
                abs(self.z - other.z) < 1e-10)
    
    def dot(self, other: 'Vec3') -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z
    
    def cross(self, other: 'Vec3') -> 'Vec3':
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x
        )
    
    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)
    
    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y + self.z * self.z
    
    def normalized(self) -> 'Vec3':
        length = self.length()
        if length < 1e-10:
            return Vec3(0, 0, 0)
        return Vec3(self.x / length, self.y / length, self.z / length)
    
    def lerp(self, other: 'Vec3', t: float) -> 'Vec3':
        t = max(0.0, min(1.0, t))
        return Vec3(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t
        )
    
    def distance_to(self, other: 'Vec3') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def distance_sq_to(self, other: 'Vec3') -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return dx * dx + dy * dy + dz * dz
    
    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)
    
    def to_list(self) -> list:
        return [self.x, self.y, self.z]
    
    @classmethod
    def from_tuple(cls, data: Tuple[float, float, float]) -> 'Vec3':
        return cls(data[0], data[1], data[2])
    
    @classmethod
    def from_list(cls, data: list) -> 'Vec3':
        return cls(data[0], data[1], data[2])
    
    ZERO: 'Vec3' = None
    ONE: 'Vec3' = None
    UP: 'Vec3' = None
    DOWN: 'Vec3' = None
    LEFT: 'Vec3' = None
    RIGHT: 'Vec3' = None
    FORWARD: 'Vec3' = None
    BACK: 'Vec3' = None


Vec3.ZERO = Vec3(0, 0, 0)
Vec3.ONE = Vec3(1, 1, 1)
Vec3.UP = Vec3(0, 1, 0)
Vec3.DOWN = Vec3(0, -1, 0)
Vec3.LEFT = Vec3(-1, 0, 0)
Vec3.RIGHT = Vec3(1, 0, 0)
Vec3.FORWARD = Vec3(0, 0, 1)
Vec3.BACK = Vec3(0, 0, -1)
