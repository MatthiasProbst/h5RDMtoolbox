"""main"""
import pathlib
import shutil
import yaml

from utils import get_specialtype_function_info
from h5rdmtoolbox._user import UserDir


def write_convention_module_from_yaml(yaml_filename: pathlib.Path):
    yaml_filename = pathlib.Path(yaml_filename)
    convention_name = yaml_filename.stem

    print(f'Convention "{convention_name}" filename: {yaml_filename}')

    print('creating directory for the convention')
    # create the convention directory where to build the validators
    convention_dir = UserDir.user_dirs['conventions'] / convention_name
    convention_dir.mkdir(parents=True, exist_ok=True)

    target_convention_filename = convention_dir / 'convention.py'

    special_validator_filename = yaml_filename.parent / f'{convention_name}_vfuncs.py'
    if special_validator_filename.exists():
        print(f'Found special functions file: {special_validator_filename}')
        shutil.copy(special_validator_filename, target_convention_filename)
    else:
        print('No special functions defined')
        # touch file:
        with open(convention_dir / f'convention.py', 'w'):
            pass

    validator_dict = {}

    # special validator functions are defined in the test_convention_vfuncs.py file
    # read it and create the validator classes:

    special_type_info = get_specialtype_function_info(target_convention_filename)
    with open(convention_dir / f'convention.py', 'a') as f:
        f.writelines('\n# ---- generated code: ----\nfrom h5rdmtoolbox.conventions.toolbox_validators import *\n')
        f.writelines("""
    
from pydantic import BaseModel
# from pydantic.functional_validators import WrapValidator
# from typing_extensions import Annotated

""")
    with open(convention_dir / f'convention.py', 'a') as f:
        # write type definitions from YAML file:
        for k, v in special_type_info.items():
            # lines = f"""\n\n{k} | {v} | unit = Annotated[str, WrapValidator(validate_units)]\n\n"""
            lines = f"""{k.strip('validate_')} = Annotated[str, WrapValidator({k})]\n"""
            f.writelines(lines)

    # read the yaml file:
    with open(yaml_filename, 'r') as f:
        convention_dict = yaml.safe_load(f)

    standard_attributes = {}
    type_definitions = {}
    for k, v in convention_dict.items():
        if isinstance(v, dict):
            # can be a type definition or a validator
            if k.startswith('$'):
                print(k, v)
                # it is a type definition
                # if it is a dict of entries, it is something like this:
                # class User(BaseModel):
                #     name: str
                #     personal_details: PersonalDetails
                if isinstance(v, dict):
                    type_definitions[k] = v

            else:
                if 'regex' in v['validator']:
                    import re

                    regex_validator = 'regex_00'  # TODO use proper id
                    match = re.search(r'regex\((.*?)\)', v['validator'])
                    re_pattern = match.group(1)
                    standard_attributes[k] = regex_validator
                    _v = v.copy()
                    _v['validator'] = regex_validator
                    standard_attributes[k] = _v
                    with open(convention_dir / f'convention.py', 'a') as f:
                        f.writelines(f"""import re\n\ndef {regex_validator}_validator(value, parent=None, attrs=None):
    pattern = re.compile(r'{re_pattern}')
    if not pattern.match(value):
        raise ValueError('Invalid format for pattern')
    return value


{regex_validator} = Annotated[int, WrapValidator({regex_validator}_validator)]""")
                else:
                    standard_attributes[k] = v

    # get validator and write them to convention-python file:
    with open(convention_dir / f'convention.py', 'a') as f:
        # write type definitions from YAML file:
        for k, v in type_definitions.items():
            validator_name = k.strip('$').capitalize()
            validator_dict[k] = f'{validator_name}Validator'
            lines = f"""
    
class {validator_name}Validator(BaseModel):
    """ + '\n    '.join([f'{k}: {v}' for k, v in v.items()])
            # write imports to file:
        f.writelines(lines)

        for stda_name, stda in standard_attributes.items():
            validator_class_name = stda_name.capitalize() + 'Validator'
            _type = stda["validator"]
            if _type in type_definitions:
                continue

            _type_str = _type.strip("$")
            validator_dict[stda_name] = validator_class_name
            lines = [
                # testing:
                # f'\nprint(special_type_funcs.units("123", None, None))'
                f'\n\n\nclass {validator_class_name}(BaseModel):',
                f'\n    """{stda["description"]}"""',
                f'\n    value: {_type_str}',
                # f'\n\n{validator_class_name}(value="hallo")'

            ]
            f.writelines(lines)
        f.writelines('\n\n\n')
        f.writelines('UnitsValidator(value="1")\n')
        f.writelines(f'validator_dict = {validator_dict}\n')


if __name__ == '__main__':
    write_convention_module_from_yaml('test_convention.yaml')
