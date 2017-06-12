# -*- coding: utf-8 -*-
import unittest
import textwrap

from functools import partial

from calmjs.parse import es5
from calmjs.parse.asttypes import FunctionCall
from calmjs.parse.asttypes import String
from calmjs.parse.visitors.generic import ReprVisitor
from calmjs.parse.visitors.generic import ConditionalVisitor

from calmjs.webpack.visitor import _replace_list_item
from calmjs.webpack.visitor import _replace_list_items
from calmjs.webpack.visitor import _replace_obj_attr
from calmjs.webpack.visitor import ReplacementVisitor

astrepr = partial(ReprVisitor().visit, indent=2)


class ReplacementHelperTestCase(unittest.TestCase):

    def test_replace_list_item(self):
        items = [1, 3, 5]
        _replace_list_item(items, 1, None)
        self.assertEqual(items, [1, 3, 5])
        _replace_list_item(items, 1, 'str')
        self.assertEqual(items, [1, 'str', 5])

    def test_replace_list_items(self):
        class Foo(object):
            pass

        item_a = tuple([1, 2])
        item_b = tuple([9, 3])
        item_c = tuple([2, 1])
        o = Foo()
        o.items = [item_a, item_b, item_c]
        replacements = {
            item_b: tuple(['replaced', 'thing']),
        }
        _replace_list_items(o, 'items', {})
        self.assertEqual(o.items, [item_a, item_b, item_c])
        _replace_list_items(o, 'items', replacements)
        self.assertEqual(o.items, [item_a, replacements[item_b], item_c])

    def test_replace_obj_attr(self):
        class Foo(object):
            pass

        o = Foo()
        attr1 = Foo()
        attr2 = Foo()
        attr3 = Foo()
        o.attr1 = attr1
        o.attr2 = attr2

        replacements = {attr2: attr3}

        # mimic real usage
        _replace_obj_attr(o, 'attr1', replacements)
        self.assertEqual(o.attr1, attr1)
        self.assertEqual(o.attr2, attr2)

        _replace_obj_attr(o, 'attr2', replacements)
        self.assertEqual(o.attr1, attr1)
        self.assertEqual(o.attr2, attr3)


class ReplacementTestCase(unittest.TestCase):

    def test_probe_commonjs_static(self):
        cond = ConditionalVisitor()
        tree = es5("""
        f1();
        f2();
        f3();
        f4();
        """)
        # our target is the third function call (skip 2)
        node = cond.extract(tree, lambda n: isinstance(n, FunctionCall), 2)
        nodemap = {
            node: String('"test string"')
        }

        replacer = ReplacementVisitor()
        replacer.replace(tree, nodemap)
        # reparse
        self.assertEqual(str(tree), textwrap.dedent("""
        f1();
        f2();
        "test string";
        f4();
        """).strip())
