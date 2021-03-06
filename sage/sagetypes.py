"""
Exporting metadata from Sage

EXAMPLES::

    sage: from sagetypes import Exporter
    sage: e = Exporter()
    sage: e.harvest_categories()
    sage: e.harvest_sage_object(TransitiveGroups())
    sage: for P in [ TransitiveGroup(4,1), Partitions(100), QQ['x,y'] ]:
    ....:     _ = e.harvest_sage_object(P)
    ....:     _ = e.harvest_sage_object(P.an_element())
    sage: e.save('transitive_groups.json')

..  TODO::

    - Instrument TestSuite calls to harvest the whole Sage library
    - How to separate mathematical metadata from technical stuff
    - Currently, the metadata for an instance is added to that of its class;
      if there are several instances with the same class, the last one wins
"""

import json
from sage.misc.misc import attrcall
from sage.misc.cachefunc import cached_function
from sage.misc.abstract_method import AbstractMethod
from sage.misc.sageinspect import sage_getargspec
from sage.categories.category import Category, JoinCategory
from sage.categories.category_with_axiom import CategoryWithAxiom
from sage.categories.covariant_functorial_construction import FunctorialConstructionCategory
from sage.sets.recursively_enumerated_set import RecursivelyEnumeratedSet
from sage.categories.rings import Rings
from sage.structure.parent import Parent
from sage.structure.sage_object import SageObject
# import mygap



def related_categories(category):
    result = list(category.super_categories())
    for key,value in category.__class__.__base__.__dict__.iteritems():
        if isinstance(value, type):
            if issubclass(value, (CategoryWithAxiom, FunctorialConstructionCategory)):
                if key == "Algebras":
                    result.append(getattr(category, key)(Rings()))
                else:
                    result.append(getattr(category, key)())
    return result

axioms_of_magmas = ['Associative', 'Finite', 'Inverse','Unital','FinitelyGenerated','Commutative']
#,'CartesianProducts','Metric','Topological','Quotients','Subquotients','Subobjects','IsomorphicObjects']

def sub_categories_of_magmas(cat):
    result = []
    for ax in axioms_of_magmas:
        try:
            result.append(getattr(cat, ax)())
        except AttributeError:
            pass
    return result


@cached_function
def category_sample():
    r"""
    Return a sample of categories.

    It is constructed by looking for all concrete category classes
    declared in ``sage.categories.all``, calling
    :meth:`Category.an_instance` on those and taking all their super
    categories.

    EXAMPLES::

        sage: from sage.categories.category import category_sample
        sage: sorted(category_sample(), key=str)
        [Category of G-sets for Symmetric group of order 8! as a permutation group,
         Category of Hecke modules over Rational Field,
         Category of additive magmas, ...,
         Category of fields, ...,
         Category of graded hopf algebras with basis over Rational Field, ...,
         Category of modular abelian varieties over Rational Field, ...,
         Category of simplicial complexes, ...,
         Category of vector spaces over Rational Field, ...,
         Category of weyl groups,...
    """
    import sage.categories.all
    abstract_classes_for_categories = [Category]
    seeds = {cls.an_instance()
             for cls in sage.categories.all.__dict__.values()
             if isinstance(cls, type) and issubclass(cls, Category) and cls not in abstract_classes_for_categories}
    return list(RecursivelyEnumeratedSet(seeds, related_categories))

def category_name(category):
    """
    Return the name for the category

    EXAMPLES::

        sage: sagetypes.category_name(Groups())
        'sage.categories.groups.Groups'
    """
    return class_name(category.__class__.__base__)

def class_name(cls):
    """
    Return the full name of a class or global function

    """
    return cls.__module__+"."+cls.__name__

class Exporter(object):
    """
    A class to iteratively/recursively harvest and export semantic
    information from Sage by introspection.

    EXAMPLES::

        sage: from sagetypes import Exporter

    At first, the exporter starts with an empty database::

        sage: e = Exporter()
        sage: e._database
        {'categories': {}, 'classes': {}, 'functions': {}}

    Let's harvest metadata from a class:

        sage: e.harvest_class(Parent)
        sage: e._database['classes'].keys()
        ['sage.structure.parent.Parent',
         'sage.structure.sage_object.SageObject',
         'sage.structure.category_object.CategoryObject']

    Now we can save the current database, and reload it later::

        sage: e.save("test.json")
        sage: f = Exporter("test.json")
        sage: f._database['classes'].keys()
        ['sage.structure.parent.Parent',
         'sage.structure.sage_object.SageObject',
         'sage.structure.category_object.CategoryObject']
    """
    def __init__(self, file=None):
        if file is None:
            self._database = {
                'categories': {},
                'classes' : {},
                'functions': {},
                }
        else:
            self._database = json.load(file)

    def save(self, file):
        import json
        with open(file, 'w') as outfile:
            json.dump(self._database, outfile, sort_keys=True, indent=4, separators=(',', ': '), default=str, allow_nan=True)

    def harvest_category(self, category):
        """
        Harvest and return the metadata contained in ``category``.

        As a side effect, all the super categories are harvested as
        well, and the information stored in the exporter's database.

        EXAMPLES::

            sage: from sagetypes import export_category
            sage: export_category(Groups())
            {'implied': ['sage.categories.monoids.Monoids',
                         'sage.categories.magmas.Magmas.Unital.Inverse'],
             'name': 'sage.categories.groups.Groups',
             'type': 'Sage_Category'}
        """
        database = self._database['categories']
        name = category_name(category)
        if name in database:
            return database[name]
        semantic = getattr(category, "_semantic", {})
        data = {
              "name": name,
              "implied": [self.harvest_category(cat)['name']
                          for cat in category.super_categories()],
              "__doc__": category.__doc__,
              "axioms": list(category.axioms()),
              "structure": [category_name(cat) for cat in category.structure()],
              "type": "Sage_Category",
              "parent_class":      self.harvest_class(category.parent_class),
              "element_class":     self.harvest_class(category.element_class),
              "morphism_class":    self.harvest_class(category.morphism_class),
              "subcategory_class": self.harvest_class(category.subcategory_class),
              "gap": semantic.get("gap", None),
              "mmt": semantic.get("mmt", None)
        }
        database[name] = data
        return data

    def harvest_class(self, cls):
        """
        Harvest and return the metadata contained in 'cls'.

        As a side effect, all the super classes are harvested as well,
        and the semantic stored in the exporter's database.

        EXAMPLES::

            sage: class A:
            ....:     _semantic = {'truc': {'gap': 'coucou'} }
            ....:     def truc(x,y): pass
            ....:     def blah(x): pass
            sage: from sagetypes import Exporter
            sage: Exporter().harvest_class(A)
            {'__doc__': None,
             'methods': {'blah': {'__doc__': None,
               'args': ['x'],
               'argspec': ArgSpec(args=['x'], varargs=None, keywords=None, defaults=None)},
              'truc': {'__doc__': None,
               'args': ['x', 'y'],
               'argspec': ArgSpec(args=['x', 'y'], varargs=None, keywords=None, defaults=None),
               'gap': 'coucou'}}}
        """
        database = self._database['classes']
        name = class_name(cls)
        if name in database:
            return database[name]
        semantic = getattr(cls, "_semantic", {})
        data = {
            "name": name,
            "__doc__": getattr(cls, "__doc__", None),
              "implied": [self.harvest_class(c)['name']
                          for c in cls.__bases__
                              if issubclass(c, SageObject)],
            "methods": { key:
                self.harvest_function(method, semantic.get(key, {}), store=False)
                for (key, method) in cls.__dict__.iteritems()
                if key not in ["__doc__", "__module__", "_sage_src_lines_", "_reduction"]
                and (callable(method) or isinstance(method, AbstractMethod))
                and not any(hasattr(base, key) for base in cls.__bases__)
            }
        }
        database[name] = data
        return data

    def harvest_sage_object(self, obj):
        r"""
        Harvest the metadata contained in the Sage Object `obj`.

        As a side effect, the class of `obj` is harvested as well, and the
        semantic stored in the exporter's database.

        EXAMPLES::

            sage: from sagetypes import Exporter; e = Exporter()
            sage: e.harvest_sage_object(QQ)
            sage: e._database['classes']['sage.rings.rational_field.RationalField_with_category']
            {'__doc__': ...,
             'categories': ['sage.categories.quotient_fields.QuotientFields',
                            'sage.categories.metric_spaces.MetricSpaces'],
             'implied': ['sage.rings.rational_field.RationalField'],
             'methods': {},
             'name': 'sage.rings.rational_field.RationalField_with_category'
            }
        """
        cls = obj.__class__
        data = self.harvest_class(cls)
        if isinstance(obj, Parent):
            category = obj.category()
            categories = category.super_categories() if isinstance(category, JoinCategory) else [category]
            data['categories'] = [self.harvest_category(category)['name']
                                  for category in categories]
        try:
            construction = obj.construction()
        except AttributeError:
            construction = None
        if construction:
            data['construction'] = [self.harvest_sage_object(x)['name'] for x in construction]
        return data

    def harvest_function(self, method, semantic={}, store=True):
        """
        Harvest metadata about a single function/method, including stuff in
        `semantic`

        INPUT:

            - ``store`` -- a boolean (default: True): whether to store
              the harvested information, or just return it

        Storing is meant for global functions, non storing for methods
        of classes whose data will be stored in the class

        EXAMPLES::

            sage: def f(x,y): pass
            sage: Exporter().harvest_method(f, {"gap":"coucou"}, store=False)
            {'__doc__': None,
             'args': ['x', 'y'],
             'argspec': ArgSpec(args=['x', 'y'], varargs=None, keywords=None, defaults=None),
             'gap': 'coucou',
             'name': 'f'}
        """
        if isinstance(method, AbstractMethod):
            method = method._f
        try:
            argspec = sage_getargspec(method)
            result = {"__doc__": method.__doc__,
                      "args": argspec.args,
                      "argspec": argspec   # TODO: add code
            }
        except TypeError:
            result = {}
        result.update(semantic)

        if store:
            result['name'] = class_name(method)
            self._database['functions'][result['name']] = result
        return result

    def harvest_categories(self):
        for category in category_sample():
            self.harvest_category(category)

# Unused
def abstract_methods_of_categories(self):
    """
    Return the methods that are required and optional for parents,
    elements, morphisms, ... of this category.

    EXAMPLES::

        sage: Algebras(QQ).required_methods()
        {'element': {'optional': ['_add_', '_mul_'], 'required': ['__nonzero__']},
         'parent': {'optional': ['algebra_generators'], 'required': ['__contains__']}}
    """
    return { "parent"  : abstract_methods_of_class(self.parent_class),
             "element" : abstract_methods_of_class(self.element_class),
             "morphism": abstract_methods_of_class(self.morphism_class),
             "subcategory": abstract_methods_of_class(self.subcategory_class)
    }

# Unused
def abstract_methods_of_class(cls, extract=None):
    """
    Returns the required and optional abstract methods of the class

    EXAMPLES::

        sage: class AbstractClass:
        ...       @abstract_method
        ...       def required1(): pass
        ...
        ...       @abstract_method(optional = True)
        ...       def optional2(): pass
        ...
        ...       @abstract_method(optional = True)
        ...       def optional1(): pass
        ...
        ...       @abstract_method
        ...       def required2(): pass
        ...
        sage: sage.misc.abstract_method.abstract_methods_of_class(AbstractClass)
        {'optional': ['optional1', 'optional2'],
         'required': ['required1', 'required2']}

    """
    if extract is None:
        def extract(f):
            return f._name
    result = { "required"  : [],
               "optional"  : []
               }
    for name in dir(cls):
        entry = getattr(cls, name)
        if not isinstance(entry, AbstractMethod):
            continue
        if entry.is_optional():
            result["optional"].append(extract(entry))
        else:
            result["required"].append(extract(entry))
    return result

def category_graph(categories = None, relabel="object_names"):
    """
    Return the graph of the categories in Sage.

    INPUT:

    - ``categories`` -- a list (or iterable) of categories

    If ``categories`` is specified, then the graph contains the
    mentioned categories together with all their super
    categories. Otherwise the graph contains (an instance of) each
    category in :mod:`sage.categories.all` (e.g. ``Algebras(QQ)`` for
    algebras).

    For readability, the names of the category are shortened.

    .. TODO:: Further remove the base ring (see also :trac:`15801`).

    EXAMPLES::

        sage: G = sage.categories.category.category_graph(categories = [Groups()])
        sage: G.vertices()
        ['groups', 'inverse unital magmas', 'magmas', 'monoids', 'objects',
         'semigroups', 'sets', 'sets with partial maps', 'unital magmas']
        sage: G.plot()
        Graphics object consisting of 20 graphics primitives

        sage: sage.categories.category.category_graph().plot()
        Graphics object consisting of ... graphics primitives
    """
    from sage import graphs
    if categories is None:
        categories = category_sample()
    # Include all the super categories
    # Get rid of join categories
    categories = set(cat
                     for category in categories
                     for cat in category.all_super_categories(proper=isinstance(category, JoinCategory)))
    g = graphs.digraph.DiGraph()
    for cat in categories:
        g.add_vertex(cat)
        for source in categories:
            # Don't use super_categories() since it might contain join categories
            for target in source._super_categories:
                g.add_edge([source, target])

    if relabel == "object_names":
        g.relabel(attrcall("_repr_object_names"))
    return g
