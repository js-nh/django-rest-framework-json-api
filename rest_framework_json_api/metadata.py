from collections import OrderedDict

from django.db.models.fields import related
from django.utils.encoding import force_text
from rest_framework import serializers
from rest_framework.metadata import SimpleMetadata
from rest_framework.utils.field_mapping import ClassLookupDict

from rest_framework_json_api.utils import get_related_resource_type


class JSONAPIMetadata(SimpleMetadata):
    """
    This is the JSON:API metadata implementation.
    It returns an ad-hoc set of information about the view.
    There are not any formalized standards for `OPTIONS` responses
    for us to base this on.
    """
    type_lookup = ClassLookupDict({
        serializers.HyperlinkedIdentityField: 'Relationship',
        serializers.HyperlinkedRelatedField: 'Relationship',
        serializers.BooleanField: 'Boolean',
        serializers.NullBooleanField: 'Boolean',
        serializers.CharField: 'String',
        serializers.URLField: 'URL',
        serializers.EmailField: 'Email',
        serializers.RegexField: 'Regex',
        serializers.SlugField: 'Slug',
        serializers.IntegerField: 'Integer',
        serializers.FloatField: 'Float',
        serializers.DecimalField: 'Decimal',
        serializers.DateField: 'Date',
        serializers.DateTimeField: 'DateTime',
        serializers.TimeField: 'Time',
        serializers.ChoiceField: 'Choice',
        serializers.MultipleChoiceField: 'MultipleChoice',
        serializers.FileField: 'File',
        serializers.ImageField: 'Image',
        serializers.ListField: 'List',
        serializers.DictField: 'Dict',
        serializers.Serializer: 'Serializer',
    })

    relation_type_lookup = ClassLookupDict({
        related.ReverseManyRelatedObjectsDescriptor: 'ManyToMany',
        related.ForeignRelatedObjectsDescriptor: 'OneToMany',
        related.ReverseSingleRelatedObjectDescriptor: 'ManyToOne',
    })

    def determine_metadata(self, request, view):
        metadata = OrderedDict()
        metadata['name'] = view.get_view_name()
        metadata['description'] = view.get_view_description()
        metadata['renders'] = [renderer.media_type for renderer in view.renderer_classes]
        metadata['parses'] = [parser.media_type for parser in view.parser_classes]
        metadata['allowed_methods'] = view.allowed_methods
        if hasattr(view, 'get_serializer'):
            actions = self.determine_actions(request, view)
            if actions:
                metadata['actions'] = actions
        return metadata

    def get_serializer_info(self, serializer):
        """
        Given an instance of a serializer, return a dictionary of metadata
        about its fields.
        """
        if hasattr(serializer, 'child'):
            # If this is a `ListSerializer` then we want to examine the
            # underlying child serializer instance instead.
            serializer = serializer.child
        return OrderedDict(
            [(field_name, self.get_field_info(field, serializer)) for field_name, field in serializer.fields.items()]
        )

    def get_field_info(self, field, serializer):
        """
        Given an instance of a serializer field, return a dictionary
        of metadata about it.
        """
        field_info = OrderedDict()

        if isinstance(field, serializers.ManyRelatedField):
            field_info['type'] = self.type_lookup[field.child_relation]
        else:
            field_info['type'] = self.type_lookup[field]

        serializer_model = getattr(serializer.Meta, 'model')
        try:
            field_info['relationship_type'] = self.relation_type_lookup[getattr(serializer_model, field.field_name)]
        except KeyError:
            pass
        except AttributeError:
            pass
        else:
            field_info['relationship_resource'] = get_related_resource_type(field)

        field_info['required'] = getattr(field, 'required', False)

        attrs = [
            'read_only', 'write_only', 'label', 'help_text',
            'min_length', 'max_length',
            'min_value', 'max_value', 'initial'
        ]

        for attr in attrs:
            value = getattr(field, attr, None)
            if value is not None and value != '':
                field_info[attr] = force_text(value, strings_only=True)

        if getattr(field, 'child', None):
            field_info['child'] = self.get_field_info(field.child, field.child.serializer)
        elif getattr(field, 'fields', None):
            field_info['children'] = self.get_serializer_info(field)

        return field_info