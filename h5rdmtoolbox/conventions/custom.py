"""Generates the standard name convention file for Fluids
This is work in progress and as long as there is no official version provided by the community
this repository uses this convention
"""

from h5rdmtoolbox.conventions.standard_attributes.standard_name import StandardNameTable, StandardNameTableTranslation

FluidStandardNameTable = StandardNameTable('fluid',
                                           table={
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
                                               'xx_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'xy_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'xz_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'yx_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'yy_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'yz_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'zx_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'zy_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'zz_reynolds_stress': {'canonical_units': 'm**2/s**2',
                                                                      'description': None},
                                               'pressure': {'canonical_units': 'Pa', 'description': None},
                                               'turbulent_kinetic_energy': {'canonical_units': 'm**2/s**2',
                                                                            'description': None},
                                               'static_pressure': {'canonical_units': 'Pa', 'description': None},
                                               'static_pressure_difference': {'canonical_units': 'Pa',
                                                                              'description': None},
                                               'dynamic_pressure': {'canonical_units': 'Pa',
                                                                    'description': None},
                                               'dynamic_pressure_difference': {'canonical_units': 'Pa',
                                                                               'description': None},
                                               'total_pressure': {'canonical_units': 'Pa', 'description': None},
                                               'total_pressure_difference': {'canonical_units': 'Pa',
                                                                             'description': None},
                                               'absolute_pressure': {'canonical_units': 'Pa',
                                                                     'description': None},
                                               'absolute_pressure_difference': {'canonical_units': 'Pa',
                                                                                'description': None},
                                               'sound_pressure': {'canonical_units': 'Pa', 'description': None},
                                               'temperature': {'canonical_units': 'K', 'description': None},
                                               'ambient_temperature': {'canonical_units': 'K',
                                                                       'description': None},
                                           },
                                           version_number=1, contact='matthias.probst@kit.edu',
                                           institution='Karlsruhe Institute of Technology',
                                           valid_characters='[^a-zA-Z0-9_]',
                                           pattern='^[0-9 ].*')
piv_name_table_dict = FluidStandardNameTable.table.copy()
piv_name_table_dict.update({'x_pixel_coordinate': {'canonical_units': 'pixel', 'description': None},
                            'y_pixel_coordinate': {'canonical_units': 'pixel', 'description': None},
                            'x_displacement_of_peak1': {'canonical_units': '', 'description': None},
                            'x_displacement_of_peak2': {'canonical_units': '', 'description': None},
                            'x_displacement_of_peak3': {'canonical_units': '', 'description': None},
                            'y_displacement_of_peak1': {'canonical_units': '', 'description': None},
                            'y_displacement_of_peak2': {'canonical_units': '', 'description': None},
                            'y_displacement_of_peak3': {'canonical_units': '', 'description': None},
                            })


PIVStandardNameTable = StandardNameTable(name='piv', table=piv_name_table_dict,
                                         version_number=1, contact='matthias.probst@kit.edu',
                                         institution='Karlsruhe Institute of Technology',
                                         valid_characters='[^a-zA-Z0-9_]',
                                         pattern='^[0-9 ].*')

snttrans_pivview = StandardNameTableTranslation(pivview_to_standardnames_dict, PIVStandardNameTable)
snttrans_pivview.register(overwrite=True)

FluidStandardNameTable.register(overwrite=True)
PIVStandardNameTable.register(overwrite=True)
# standard_name_table_to_xml(FluidStandardNameTable)
# standard_name_table_to_xml(PIVStandardNameTable)
