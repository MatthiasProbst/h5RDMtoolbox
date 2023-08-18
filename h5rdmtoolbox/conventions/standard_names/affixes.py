"""module for constructors used as pre- or suffixes to standard names"""
import warnings
from dataclasses import dataclass
from typing import List, Union, Dict, Tuple, Callable

from .transformation import Transformation, StandardName, errors


def _difference_of_X_and_Y_between_LOC1_and_LOC2(match, snt) -> StandardName:
    """Difference of X and Y across device"""
    standard_name = match.string
    groups = match.groups()
    assert len(groups) == 4
    if groups[2] not in snt.locations:
        raise KeyError(f'StandardLocation "{groups[2]}" not found in registry of the standard name table. '
                       f'Available locations are: {snt.locations}')
    if groups[3] not in snt.locations:
        raise KeyError(f'StandardLocation "{groups[3]}" not found in registry of the standard name table. '
                       f'Available locations are: {snt.locations}')
    sn1 = snt[groups[0]]
    sn2 = snt[groups[1]]
    if sn1.units != sn2.units:
        raise ValueError(f'Units of "{sn1.name}" and "{sn2.name}" are not compatible: "{sn1.units}" and '
                         f'"{sn2.units}".')
    new_description = f"Difference of {sn1.name} and {sn2.name} between {groups[2]} and {groups[3]}"
    return StandardName(standard_name, sn1.units, new_description)


between_LOC1_and_LOC2 = Transformation(
    r"^difference_of_(.*)_and_(.*)_between_(.*)_and_(.*)$",
    _difference_of_X_and_Y_between_LOC1_and_LOC2,
)


def _surface_(match, snt) -> StandardName:
    """Component of a standard name, e.g. x_velocity where velocity is the
    existing standard name and x is a registered component"""
    groups = match.groups()
    assert len(groups) == 2
    surface = groups[0]
    if surface not in snt.affixes['surface'].values:
        return False
    sn = snt[groups[1]]
    if not sn.is_vector():
        raise errors.StandardNameError(f'"{sn.name}" is not a vector quantity.')
    new_description = f'{sn.description} {snt.components[surface].description}'
    return StandardName(match.string, sn.units, new_description)


surface_ = Transformation(r"^(.*)_(.*)$", _surface_)


def _component_(match, snt) -> StandardName:
    """Component of a standard name, e.g. x_velocity where velocity is the
    existing standard name and x is a registered component"""
    groups = match.groups()
    component = groups[0]
    if component not in snt.affixes['component'].values:
        raise KeyError(f'"{component}" is not a registered component. '
                       f'Available components are: {list(snt.affixes["component"].values.keys())}')
    sn = snt[groups[1]]
    if not sn.is_vector():
        raise errors.StandardNameError(f'"{sn.name}" is not a vector quantity.')
    new_description = f'{sn.description} {snt.components[component].description}'
    return StandardName(match.string, sn.units, new_description)


component_ = Transformation(r"^(.*)_(.*)$", _component_)


# def _surface_or_component(match, snt) -> StandardName:
#     """combine both because no two transformations are allowed to have the same pattern!"""
#     groups = match.groups()
#     assert len(groups) == 2
#     sn = snt[groups[1]]
#
#     s_or_c = groups[0]
#     if s_or_c not in snt.affixes.get("surfaces", []):
#         if s_or_c not in snt.affixes.get("components", []):
#             raise KeyError(f'Neither a valid surface nor component: "{s_or_c}".'
#                            f'Available surfaces are: {snt.affixes["surfaces"]} '
#                            f'and available components are: {snt.affixes["components"]}')
#     new_description = f'{sn.description} {snt.affixes["surfaces"][s_or_c].description}'
#     return StandardName(match.string, sn.units, new_description)
#
#
# surface_or_component = Transformation(r"^(.*)_(.*)$", _surface_or_component)


def _difference_of_X_across_device(match, snt) -> Union[StandardName, bool]:
    """Difference of X across device"""
    groups = match.groups()
    assert len(groups) == 2
    if groups[1] not in snt.devices:
        raise KeyError(f'Device {groups[1]} not found in registry of the standard name table. '
                       f'Available devices are: {snt.devices}.')
    try:
        sn = snt[groups[0]]
    except errors.StandardNameError:
        return False
    new_description = f"Difference of {sn.name} across {groups[1]}"
    return StandardName(match.string, sn.units, new_description)


difference_of_X_across_device = Transformation(r"^difference_of_(.*)_across_(.*)$",
                                               _difference_of_X_across_device)


def _difference_of_X_and_Y_across_device(match, snt) -> StandardName:
    """Difference of X and Y across device"""
    groups = match.groups()
    assert len(groups) == 3
    if groups[2] not in snt.devices:
        raise KeyError(f'Device {groups[2]} not found in registry of the standard name table. '
                       f'Available devices are: {snt.devices}')
    sn1 = snt[groups[0]]
    sn2 = snt[groups[1]]
    if sn1.units != sn2.units:
        raise ValueError(f'Units of "{sn1.name}" and "{sn2.name}" are not compatible: "{sn1.units}" and '
                         f'"{sn2.units}".')
    new_description = f"Difference of {sn1.name} and {sn2.name} across {groups[2]}"
    return StandardName(match.string, sn1.units, new_description)


difference_of_X_and_Y_across_device = Transformation(r"^difference_of_(.*)_and_(.*)_across_(.*)$",
                                                     _difference_of_X_and_Y_across_device)


def _X_at_LOC(match, snt) -> StandardName:
    groups = match.groups()
    assert len(groups) == 2
    sn = snt[groups[0]]
    loc = groups[1]
    if loc not in snt.locations:
        raise KeyError(f'StandardLocation "{loc}" not found in registry of the standard name table. '
                       f'Available locations are: {snt.locations}')
    new_description = f"{sn} at {loc}"
    return StandardName(match.string, sn.units, new_description)


X_at_LOC = Transformation(r"^(.*)_at_(.*)$", _X_at_LOC)


def _in_reference_frame(match, snt) -> StandardName:
    """A standard name in a standard reference frame"""
    groups = match.groups()
    assert len(groups) == 2
    sn = snt[groups[0]]
    frame = groups[1]
    if frame not in snt.affixes['reference_frame']:
        raise errors.StandardNameError(
            f'Reference Frame "{frame}" not found in registry of the standard name table. '
            f'Available reference frames are: {snt.standard_reference_frames.names}')
    new_description = f'{sn.description}. The quantity is relative to the reference frame "{frame}"'
    return StandardName(match.string, sn.units, new_description)


in_reference_frame = Transformation(r"^(.*)_in_(.*)$", _in_reference_frame)

affix_transformations = {'location': [between_LOC1_and_LOC2, X_at_LOC],
                         'component': [component_],
                         'surface': [surface_],
                         'device': [difference_of_X_across_device, difference_of_X_and_Y_across_device],
                         'reference_frame': [in_reference_frame]
                         }


def _get_transformation(name) -> List[Transformation]:
    t = affix_transformations.get(name, None)
    if t is None:
        raise ValueError(f'No transformation for affix {name}. You may need to implement it first or check the '
                         f'spelling!')
    return t


class Affix:
    """Standard constructor is a prefix or suffix to a
    standard name, e.g. [x_]velocity, velocity[_in_rotating_frame]"""

    def __init__(self, name, description: str, values: Dict, transformation: Callable):
        self._name = name
        self._description = description
        self._values = values
        self.transformation = transformation

    def __contains__(self, item):
        return item in self._values

    @staticmethod
    def from_dict(name, data: Dict):
        """Instantiate an Affix from a dictionary"""
        description = data.pop('description', None)
        if description is None:
            warnings.warn(f"Affix '{name}' has no description", UserWarning)
        return Affix(name, description, data, transformation=_get_transformation(name))

    @property
    def name(self):
        """Return the name of the standard item"""
        return self._name

    @property
    def description(self):
        """Return the description of the standard item"""
        return self._description

    @property
    def values(self):
        """Return the values of the standard item"""
        return self._values

    def __repr__(self):
        return f'<{self.__class__.__name__}: name="{self._name}", description="{self.description}">'

    def __str__(self):
        return self.name


@dataclass(frozen=True)
class Affixes:
    """Collection of Affix objects"""
    items: List[Affix]

    def __iter__(self):
        return iter(self.items)

    def __contains__(self, item):
        return item in self.names

    def __getitem__(self, item: Union[str, int]):
        if isinstance(item, int):
            return self.items[item]
        for _item in self.items:
            if _item.name == item:
                return _item
        raise KeyError(f"Item '{item}' not found")

    def __bool__(self):
        return self.items != []

    @property
    def names(self):
        """Return the names of the locations"""
        return [d.name for d in self.items]

    def to_dict(self) -> Dict:
        """Return dictionary representation of StandardLocations"""
        return {item.name: item.description for item in self.items}


EMPTYAFFIXES = Affixes([])


@dataclass
class StandardReferenceFrame:
    """Standard Reference Frame"""
    name: str
    type: str
    origin: Tuple[float, float, float]
    orientation: Dict
    principle_axis: Union[str, Tuple[float, float, float], None] = None

    def __post_init__(self):
        if not isinstance(self.origin, (list, tuple)):
            raise TypeError(f'Wrong type for "origin". Expecting tuple but got {type(self.origin)}')
        self.origin = tuple(self.origin)
        if isinstance(self.principle_axis, str):
            self.principle_axis = self.orientation[self.principle_axis]

    def to_dict(self):
        return {self.name: dict(type=self.type,
                                origin=self.origin,
                                orientation=self.orientation,
                                principle_axis=self.principle_axis)}


class StandardReferenceFrames:
    """Collection of Standard Reference Frames"""

    def __init__(self, standard_reference_frames: List[StandardReferenceFrame]):
        self._standard_reference_frames = {srf.name: srf for srf in standard_reference_frames}
        self._names = list(self._standard_reference_frames.keys())
        self._index = 0

    def __repr__(self):
        return f'<StandardReferenceFrames: {self._names}>'

    def __len__(self):
        return len(self._names)

    def __getitem__(self, item: Union[int, str]) -> StandardReferenceFrame:
        if isinstance(item, int):
            return self._standard_reference_frames[self._names[item]]
        return self._standard_reference_frames[item]

    def __contains__(self, item) -> bool:
        return item in self._names

    def __iter__(self):
        return self

    def __next__(self):
        if self._index < len(self) - 1:
            self._index += 1
            return self._standard_reference_frames[self._names[self._index]]
        self._index = -1
        raise StopIteration

    @property
    def names(self):
        """Return the names of the reference frames"""
        return self._names

    def to_dict(self) -> Dict:
        """Return dictionary representation of StandardReferenceFrames"""
        frames = [srf.to_dict() for srf in self._standard_reference_frames.values()]
        srfdict = {'standard_reference_frames': {}}
        for frame in frames:
            for k, v in frame.items():
                srfdict['standard_reference_frames'][k] = v
        return srfdict
