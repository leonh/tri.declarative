from collections import OrderedDict
from functools import total_ordering
import functools
import itertools
from tri.struct import Struct


def with_meta(class_to_decorate=None, add_init_kwargs=True):
    """
    Class decorator to enable a class (and it's sub-classes) to have a 'Meta' class attribute.
    """

    if class_to_decorate is None:
        return functools.partial(with_meta, add_init_kwargs=add_init_kwargs)

    if 'Meta' not in class_to_decorate.__dict__:
        blank_meta = type('Meta', (object, ), {})
        setattr(class_to_decorate, 'Meta', blank_meta)

    if add_init_kwargs:
        __init__orig = class_to_decorate.__init__

        def __init__(self, *args, **kwargs):
            new_kwargs = {}
            new_kwargs.update((k, v) for k, v in self.get_meta().items() if not k.startswith('_'))
            new_kwargs.update(kwargs)
            __init__orig(self, *args, **new_kwargs)

        setattr(class_to_decorate, '__init__', __init__)

    def get_meta(cls):
        merged_attributes = Struct()
        for class_ in reversed(cls.mro()):
            if hasattr(class_, 'Meta'):
                for key, value in class_.Meta.__dict__.items():
                    if key.startswith('__'):  # Skip internal attributes
                        continue
                    merged_attributes[key] = value
        return merged_attributes

    setattr(class_to_decorate, 'get_meta', classmethod(get_meta))

    return class_to_decorate


def declarative_member(class_to_decorate):
    """
        Class decorator that ensures that instances will be ordered after creation order when sorted.
    """

    next_index = itertools.count().next

    __init__orig = class_to_decorate.__init__

    def __init__(self, *args, **kwargs):
        object.__setattr__(self, '_index', next_index())
        __init__orig(self, *args, **kwargs)

    setattr(class_to_decorate, '__init__', __init__)

    # noinspection PyProtectedMember
    def __lt__(self, other):
        return self._index < other._index

    setattr(class_to_decorate, '__lt__', __lt__)

    class_to_decorate = total_ordering(class_to_decorate)

    return class_to_decorate


def declarative(member_class, parameter='members', add_init_kwargs=True):
    """
        Class decorator to enable classes to be defined in the style of django models.
        That is, @declarative classes will get an additional argument to constructor,
        containing an OrderedDict with all class members matching the specified type.
    """

    def get_members(cls):
        members = OrderedDict()
        for base in cls.__bases__:
            meta = getattr(base, 'Meta', None)
            if meta is not None:
                inherited_members = getattr(meta, parameter, {})
                members.update(inherited_members)

        def generate_member_bindings():
            for name, obj in cls.__dict__.items():
                if isinstance(obj, member_class):
                    yield name, obj

        members.update(sorted(generate_member_bindings(), key=lambda x: x[1]))

        return members

    def decorator(class_to_decorate):

        class DeclarativeMeta(type):
            def __init__(cls, name, bases, dict):
                if 'Meta' not in cls.__dict__:
                    setattr(cls, 'Meta', type('Meta', (object, ), {}))
                setattr(cls.Meta, parameter, get_members(cls))
                super(DeclarativeMeta, cls).__init__(name, bases, dict)

        new_class = DeclarativeMeta(class_to_decorate.__name__,
                                    class_to_decorate.__bases__,
                                    dict(class_to_decorate.__dict__))
        new_class = with_meta(add_init_kwargs=add_init_kwargs)(new_class)
        return new_class

    return decorator