"""Core module for the layout2 convention."""
import abc
import re
import typing

import h5py


def get_h5groups(h5group: h5py.Group, wildcard: bool = False) -> typing.List[h5py.Group]:
    """Return a list of all groups in the given group. If wildcard is True, also return all groups (recursively)"""
    groups = [h5group[k] for k in h5group.keys() if isinstance(h5group[k], h5py.Group)]
    if not wildcard:
        return groups

    def visitor(_, obj):
        """Visitor function for h5py.visititems()"""
        if isinstance(obj, h5py.Group):
            groups.append(obj)

    h5group.visititems(visitor)
    groups.append(h5group)
    return groups


def get_h5datasets(h5group: h5py.Group) -> typing.List[h5py.Dataset]:
    """Return a list of all datasets in the given group."""
    return [h5group[k] for k in h5group.keys() if isinstance(h5group[k], h5py.Dataset)]


class ValidationResult:
    """Validation Result class."""

    def __init__(self, validation, result: bool, is_optional: bool):
        self.validation = validation
        if result is False and is_optional is True:
            self.result = True
        else:
            self.result = result

    def __repr__(self):
        return f'ValidationResult({self.validation}, {self.result})'

    @property
    def succeeded(self) -> bool:
        """Return True if the validation succeeded."""
        return self.result

    @property
    def failed(self) -> bool:
        """Return True if the validation failed."""
        return not self.result


class OptReqWrapper:
    """Wrapper class for the Optional and Required decorators."""

    def __init__(self, optional):
        self.optional = optional

    def __call__(self, obj):
        if isinstance(obj, (int, float, str)):
            obj = Equal(obj)
        if not isinstance(obj, Validator):
            raise TypeError(f'Cannot make {obj} optional')
        obj.is_optional = self.optional
        return obj


Optional = OptReqWrapper(True)
Required = OptReqWrapper(False)


class Validator(abc.ABC):
    """Base class for all validators."""

    def __init__(self, reference):
        self.reference = reference

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.reference}")'

    @abc.abstractmethod
    def __call__(self, *args, **kwargs):
        pass


class Regex(Validator):

    def __call__(self, value):
        return re.match(self.reference, value) is not None


class Equal(Validator):
    """Validator that checks if the value is equal to the reference value.
    A reference value of '*' will always return True."""

    def __call__(self, value):
        if self.reference == '*':
            return True
        return value == self.reference


class In(Validator):
    """Validator that checks if the value is within the reference value."""

    def __init__(self, *reference):
        super().__init__(reference)

    def __call__(self, value):
        return value in self.reference


class Any(Validator):
    """An optional Validator that always returns True."""

    def __init__(self):
        super().__init__(None)
        self.is_optional = True

    def __repr__(self):
        return f'{self.__class__.__name__}(opt={self.is_optional})'

    def __call__(self, value):
        return True


class Validation(abc.ABC):
    """Base class for all validations."""

    def __init__(self, validator: Validator):
        if validator is Ellipsis:
            validator = Any()
        elif not isinstance(validator, Validator):
            validator = Equal(validator)
        self.validator = validator
        self.is_optional = False

    def validate(self, target: h5py.Group, validation_results: typing.List[ValidationResult]):
        """Validate the target object."""
        pass

    @property
    def is_required(self) -> bool:
        """Return True if this validation is required."""
        return not self.is_optional

    def __repr__(self):
        return f'{self.__class__.__name__}({self.validator})'


class AttributeValidation(Validation):
    """Validation class for attributes of a group or dataset."""

    def __init__(self, validator, parent: "GroupValidation"):
        super().__init__(validator)
        self.child = None
        # add this validation to the parent. this validation will be called if the parent validation succeeded:
        self.parent = parent
        parent.add(self)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.validator}, opt={self.is_optional})>'

    def add(self, child: Validation, overwrite=False):
        if self.child is not None and not overwrite:
            raise ValueError('child already exists and overwrite is False')
        if not isinstance(child, Validation):
            raise TypeError(f'child must be a Validation, not {type(child)}')
        self.child = child

    def validate(self, target,
                 validation_results: typing.List[ValidationResult]) -> typing.List[ValidationResult]:
        """Validate the attribute."""
        if isinstance(target, (h5py.Group, h5py.Dataset)):
            attribute_names = list(target.attrs.keys())
            if len(attribute_names) == 0:
                validation_results.append(ValidationResult(self, False, self.is_optional))
                return validation_results

            valid_flags = []
            for k in attribute_names:
                # we need to run through all attributes before we can set the result of this validation:
                is_valid = self.validator(k)
                valid_flags.append(is_valid)
                if is_valid:
                    # validation succeeded:
                    if self.child is not None:
                        validation_results = self.child.validate(target.attrs[k], validation_results)
            # now we ran through all attributes and can set the result of this validation:
            validation_results.append(ValidationResult(self, any(valid_flags), self.is_optional))

        else:
            # validate the value of an attribute
            is_valid = self.validator(target)
            validation_results.append(ValidationResult(self, is_valid, self.is_optional))
        return validation_results

    def dumps(self, indent):
        """Prints the validation specification to a string"""
        print(' ' * indent + self.__repr__())
        if self.child:
            self.child.dumps(indent + 2)


class PropertyValidation(Validation):

    def __init__(self, name, validator, parent):
        super().__init__(validator)
        self.name = name
        # add this validation to the parent. this validation will be called if the parent validation succeeded:
        self.parent = parent
        parent.add(self)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.validator})>'

    def validate(self, target: h5py.Dataset,
                 validation_results: typing.List[ValidationResult]) -> typing.List[ValidationResult]:
        if not isinstance(target, h5py.Dataset):
            raise TypeError(f'PropertyValidation can only be applied to datasets, not {type(target)}')

        prop = target.__getattribute__(self.name)
        is_valid = self.validator(prop)
        validation_results.append(ValidationResult(self, is_valid, self.is_optional))
        return validation_results

    def dumps(self, indent):
        """Prints the validation specification to a string"""
        print(' ' * indent + self.__repr__())


class AttributeValidationManager:
    """Attribute validation manager for a group or dataset validation

    Parameters
    ----------
    parent : Validation
        The parent validation object (group or dataset)
    """

    def __init__(self, parent: "Validation"):
        self.parent = parent

    def add(self,
            name_validator: typing.Union[str, Validator],
            value_validator: typing.Union[int, float, str, Validator]):
        av = AttributeValidation(name_validator, self.parent)
        if value_validator is Ellipsis:
            value_validator = Any()
        elif isinstance(value_validator, (str, int, float)):
            value_validator = Equal(value_validator)
        AttributeValidation(value_validator, av)

    def __setitem__(self, name_validator, value_validator):
        self.add(name_validator, value_validator)

    def __getitem__(self, name_validator):
        AttributeValidation(name_validator, self.parent)


class _BaseGroupAndDatasetValidation(Validation):

    def __init__(self,
                 validator: Validator,
                 parent: Validation):
        super().__init__(validator)
        self.parent = parent
        self.children = []
        try:
            self.is_optional = validator.is_optional
        except AttributeError:
            pass

    def __repr__(self):
        return f'{self.__class__.__name__}({self.validator}, opt={self.is_optional})>'

    @property
    def path(self) -> str:
        """Return the path of the parent group or dataset"""
        if self.parent is None:
            return '/'
        return '' + self.parent.path

    @property
    def attrs(self) -> AttributeValidationManager:
        """Attribute validation manager for this group or dataset"""
        return AttributeValidationManager(self)

    def add_child(self, child: Validation) -> Validation:
        """Add a child validation object to be called after this validation succeeded

        Parameters
        ----------
        child : Validation
            The child validation object to be called after this validation succeeded

        Returns
        -------
        Validation
            The child validation object.

        """
        if not isinstance(child, Validation):
            raise TypeError(f'child must be a Validation, not {type(child)}')

        for registrated_child in self.children:
            if registrated_child.parent == child.parent and registrated_child.validator.reference == child.validator.reference:
                return registrated_child
        self.children.append(child)
        return child

    add = add_child  # alias

    def dumps(self, indent):
        """Prints the validation specification to a string"""
        print(' ' * indent + self.__repr__())
        for child in self.children:
            child.dumps(indent=indent + 2)


class DatasetValidation(_BaseGroupAndDatasetValidation):
    """Dataset validation"""

    def validate(self, h5group: h5py.Group,
                 validation_results: typing.List[ValidationResult]) -> typing.List[ValidationResult]:
        """Validate datasets of a group"""
        valid_flags = []
        for dataset in get_h5datasets(h5group):
            is_valid = self.validator(dataset.name.rsplit('/', 1)[-1])
            valid_flags.append(is_valid)
            if is_valid:
                for child in self.children:
                    validation_results = child.validate(dataset, validation_results)
        validation_results.append(ValidationResult(self, any(valid_flags), self.is_optional))
        return validation_results


class GroupValidation(_BaseGroupAndDatasetValidation):
    """Group validation

    Parameters
    ----------
    validator : Validator
        The validator to be applied to the group name
    parent : GroupValidation
        The parent validation object
    """

    def validate(self, target, validation_results) -> typing.List[ValidationResult]:
        wildcard = False
        if isinstance(self.validator, Equal):
            if self.validator.reference == '*':
                wildcard = True

        groups = set(get_h5groups(target, wildcard))
        if len(groups) == 0 and self.is_required:
            validation_results.append(ValidationResult(self, False, self.is_optional))
            return validation_results

        valid_flags = []
        for group in groups:
            group_name = group.name.strip('/')
            if group_name == '':
                group_name = '/'
            is_valid = self.validator(group_name)
            valid_flags.append(is_valid)
            if is_valid:
                # validation succeeded:
                for child in self.children:
                    validation_results = child.validate(group, validation_results)

        validation_results.append(ValidationResult(self, any(valid_flags), self.is_optional))
        return validation_results

    def define_dataset(self, name: typing.Union[str, Validator, None] = None, **properties) -> DatasetValidation:
        """Add a dataset specification

        Parameters
        ----------
        name : str, Validator, optional=None
            The name of the dataset, by default None
        **properties
            The dictionary containing the properties of an HDF5 dataset and their validators

        Returns
        -------
        DatasetValidation
            The dataset validation object
        """
        if name is None:
            name = Any()
        dv = DatasetValidation(name, self)
        dv = self.add(dv)
        for name, value in properties.items():
            _ = PropertyValidation(name, value, dv)
        return dv

    def define_group(self, name: typing.Union[str, Validator]) -> "GroupValidation":
        """Add a group validation object"""
        if isinstance(name, str):
            name = Equal(name)
        gv = GroupValidation(name, self)
        return self.add(gv)


class Layout(GroupValidation):
    """Layout validation main interface class to user"""

    def __init__(self):
        super().__init__(Equal(None), None)
        self._validation_results = []

    def __repr__(self):
        return f'Layout({self.children})'

    def define_group(self, name: typing.Union[str, Validator]) -> GroupValidation:
        """Add a group validation object"""
        if isinstance(name, str):
            name = Equal(name)
        gv = GroupValidation(name, self)
        return self.add(gv)

    def __getitem__(self, item: typing.Union[str, Validator]) -> Validation:
        # TODO if not yet registered, register it, otherwise return existing
        if item == '/':
            return self
        return self.define_group(item)

    def validate(self, target: h5py.Group) -> typing.List[ValidationResult]:
        """Validate the file using this layout specification"""
        if not isinstance(target, h5py.Group):
            with h5py.File(target) as f:
                return self.validate(f)

        assert target.name == '/'
        self._validation_results = []
        for child in self.children:
            self._validation_results = child.validate(target, self._validation_results)
        return self.validation_results

    @property
    def validation_results(self) -> typing.List[ValidationResult]:
        """List of validation results"""
        return [r for r in self._validation_results if r.validation.is_required]

    @property
    def fails(self) -> int:
        """Number of failed validations"""
        return sum([int(r.failed) for r in self.validation_results])

    def get_failed(self) -> typing.List[ValidationResult]:
        """Get failed validations"""
        return [r for r in self.validation_results if r.failed]

    def dumps(self):
        """Prints the validation specification to the console"""
        for child in self.children:
            child.dumps(0)