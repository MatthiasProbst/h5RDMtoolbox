from . import conventions

cv = conventions.Convention('tbx')

# FILE
cv['__init__'].add(
    attr_cls=conventions.title.TitleAttribute,
    # target_cls=File,
    add_to_method=True,
    position={'before': 'layout'},
    optional=True
)

cv['__init__'].add(attr_cls=conventions.StandardAttribute.AnyString('institution'),
                   add_to_method=True,
                   position={'before': 'layout'},
                   optional=True)
cv['__init__'].add(attr_cls=conventions.references.ReferencesAttribute,
                   add_to_method=True,
                   position={'before': 'layout'},
                   optional=True)
cv['__init__'].add(attr_cls=conventions.tbx.StandardNameTableAttribute,
                   add_to_method=True,
                   position={'before': 'layout'},
                   optional=True)
cv['__init__'].add(attr_cls=conventions.comment.CommentAttribute,
                   add_to_method=True,
                   position={'after': 'standard_name_table'},
                   optional=True)
cv['__init__'].add(attr_cls=conventions.contact.ContactAttribute,
                   add_to_method=True,
                   position={'after': 'mode'},
                   optional=True)
cv['__init__'].add(attr_cls=conventions.source.SourceAttribute,
                   add_to_method=True,
                   position={'after': 'comment'},
                   optional=True)

# Dataset
cv['create_dataset'].add(attr_cls=conventions.tbx.StandardNameTableAttribute,
                         add_to_method=False)
cv['create_dataset'].add(attr_cls=conventions.tbx.StandardNameAttribute,
                         # target_cls=Dataset,
                         position={'after': 'data'},
                         add_to_method=True,
                         optional=False,
                         alt='long_name')
cv['create_dataset'].add(attr_cls=conventions.long_name.LongNameAttribute,
                         # target_cls=Dataset,
                         add_to_method=True,
                         position={'after': 'standard_name'},
                         optional=False,
                         alt='standard_name')
cv['create_string_dataset'].add(attr_cls=conventions.long_name.LongNameAttribute,
                                # target_cls=Dataset,
                                add_to_method='create_string_dataset',
                                position={'after': 'data'},
                                optional=True,
                                overwrite=True)
cv['create_dataset'].add(attr_cls=conventions.comment.CommentAttribute,
                         # target_cls=Dataset,
                         add_to_method=True,
                         position={'after': 'long_name'},
                         optional=True)
cv['create_dataset'].add(attr_cls=conventions.contact.ContactAttribute,
                         # target_cls=Dataset,
                         add_to_method=True,
                         position={'after': 'comment'},
                         optional=True)
cv['create_dataset'].add(attr_cls=conventions.source.SourceAttribute,
                         # target_cls=Dataset,
                         add_to_method=True,
                         position={'after': 'comment'},
                         optional=True)

# cv._methods[h5tbx.wrapper.core.Group]['create_dataset']['units']['optional'] = False
cv.make_required('create_dataset', 'units')

# cv['create_dataset'].add(attr_cls=conventions.units.ScaleAttribute,
#                          # target_cls=Dataset,
#                          add_to_method=True,
#                          position={'after': 'data'},
#                          optional=True)
# cv['create_dataset'].add(attr_cls=conventions.units.OffsetAttribute,
#                          # target_cls=Dataset,
#                          add_to_method=True,
#                          position={'after': 'data'},
#                          optional=True)

# Group
cv['create_group'].add(attr_cls=conventions.comment.CommentAttribute,
                       add_to_method=True,
                       position={'after': 'name'},
                       optional=True)
cv['create_group'].add(attr_cls=conventions.contact.ContactAttribute,
                       add_to_method=True,
                       position={'before': 'attrs'},
                       optional=True)
cv.register()
