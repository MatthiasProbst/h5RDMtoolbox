"""Generates the standard name convention file for Fluids
This is work in progress and as long as there is no official version provided by the community
this repository uses this convention
"""

from h5rdmtoolbox.conventions.standard_names import StandardNameConvention

fluid_standard_names_dict = {
    'time': {'canonical_units': 's', 'description': 'physical time'},
    'x_velocity': {'canonical_units': 'm/s',
                   'description': 'velocity is a vector quantity. x indicates the component in x-axis direction'},
    'y_velocity': {'canonical_units': 'm/s',
                   'description': 'velocity is a vector quantity. y indicates the component in y-axis direction'},
    'z_velocity': {'canonical_units': 'm/s',
                   'description': 'velocity is a vector quantity. z indicates the component in z-axis direction'},
    'z_vorticity': {'canonical_units': '1/s',
                    'description': 'vorticity is a vector quantity. z indicates the component in z-axis direction'},
    'magnitude_of_velocity': {'canonical_units': 'm/s',
                              'description': 'Magnitude of the vector quantity velocity.'},
    'x_derivative_of_x_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of x velocity in x axis direction.'},
    'y_derivative_of_x_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of x velocity in y axis direction.'},
    'z_derivative_of_x_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of x velocity in z axis direction.'},
    'x_derivative_of_y_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of y velocity in x axis direction.'},
    'y_derivative_of_y_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of y velocity in y axis direction.'},
    'z_derivative_of_y_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of y velocity in z axis direction.'},
    'x_derivative_of_z_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of z velocity in x axis direction.'},
    'y_derivative_of_z_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of z velocity in y axis direction.'},
    'z_derivative_of_z_velocity': {'canonical_units': '1/s',
                                   'description': 'Derivative of z velocity in z axis direction.'},
    'q_criterion': {'canonical_units': '1/s**2',
                    'description': 'Three dimensional Q-Criterion'},
    'q_criterion_z': {'canonical_units': '1/s**2',
                      'description': 'Two dimensional Q-Criterion in z plane.'},
    'x_coordinate': {'canonical_units': 'm', 'description': None},
    'y_coordinate': {'canonical_units': 'm', 'description': None},
    'z_coordinate': {'canonical_units': 'm', 'description': None},
    'xx_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'xy_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'xz_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'yx_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'yy_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'yz_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'zx_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'zy_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'zz_reynolds_stress': {'canonical_units': 'm**2/s**2', 'description': None},
    'pressure': {'canonical_units': 'Pa', 'description': None},
    'turbulent_kinetic_energy': {'canonical_units': 'm**2/s**2', 'description': None},
    'static_pressure': {'canonical_units': 'Pa', 'description': None},
    'static_pressure_difference': {'canonical_units': 'Pa', 'description': None},
    'dynamic_pressure': {'canonical_units': 'Pa', 'description': None},
    'dynamic_pressure_difference': {'canonical_units': 'Pa', 'description': None},
    'total_pressure': {'canonical_units': 'Pa', 'description': None},
    'total_pressure_difference': {'canonical_units': 'Pa', 'description': None},
    'absolute_pressure': {'canonical_units': 'Pa', 'description': None},
    'absolute_pressure_difference': {'canonical_units': 'Pa', 'description': None},
    'sound_pressure': {'canonical_units': 'Pa', 'description': None},
    'temperature': {'canonical_units': 'K', 'description': None},
    'ambient_temperature': {'canonical_units': 'K', 'description': None},
}

piv_standard_names_dict = fluid_standard_names_dict.copy()
piv_standard_names_dict.update({'x_pixel_coordinate': {'canonical_units': 'pixel', 'description': None},
                                'y_pixel_coordinate': {'canonical_units': 'pixel', 'description': None},
                                'x_displacement_of_peak1': {'canonical_units': '', 'description': None},
                                'x_displacement_of_peak2': {'canonical_units': '', 'description': None},
                                'x_displacement_of_peak3': {'canonical_units': '', 'description': None},
                                'y_displacement_of_peak1': {'canonical_units': '', 'description': None},
                                'y_displacement_of_peak2': {'canonical_units': '', 'description': None},
                                'y_displacement_of_peak3': {'canonical_units': '', 'description': None},
                                })



if __name__ == '__main__':
    """creating xml convention files in xml/folder which will be installed with the package.
    So if something is changed here, update the version (also repo versioN), write the xml file and re-install the 
    package"""
    import pathlib

    fluid_convention = StandardNameConvention(fluid_standard_names_dict, name='Fluid_Standard_Name',
                                              version=1, contact='matthias.probst@kit.edu',
                                              institution='Karlsruhe Institute of Technology')
    _ = fluid_convention.to_xml(pathlib.Path(__file__).parent / 'snxml' / f'fluid-v{fluid_convention.version}.xml')
    piv_convention = StandardNameConvention(piv_standard_names_dict, name='PIV_Standard_Name',
                                            version=1, contact='matthias.probst@kit.edu',
                                            institution='Karlsruhe Institute of Technology')
    _ = piv_convention.to_xml(pathlib.Path(__file__).parent / 'snxml' / f'piv-v{piv_convention.version}.xml')
