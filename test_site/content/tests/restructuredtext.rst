title: reStructuredText Test Page
slug: rst
category: tests
tags: [rest, sample]
rst_initial_header_level: 2
---

This is the reStructuredText test page
======================================
This page tests

* That reStructuredText rendering works.
* That I know how to make a RST document.
* Python code highlighting works.

.. contents:: Page contents (automatically built by rst):
    :backlinks: top
    :local:


Tables
------

(see http://docutils.sourceforge.net/docs/ref/rst/directives.html#tables)


Simple
......


+---------+----------+----------+
| column1 | column 2 | column 3 |
+=========+==========+==========+
| Peter   | 17       | London   |
+---------+----------+----------+
| Jane    | 31       | Rome     |
+---------+----------+----------+


table directive
...............

.. table:: Truth table for "not"

   =====  =====
     A    not A
   =====  =====
   False  True
   True   False
   =====  =====



csv table directive
...................

.. csv-table:: Frozen Delights!
   :header: "Treat", "Quantity", "Description"
   :widths: 15, 10, 30

   "Albatross", 2.99, "On a stick!"
   "Crunchy Frog", 1.49, "If we took the bones out, it wouldn't be
   crunchy, now would it?"
   "Gannet Ripple", 1.99, "On a stick!"



list table directive
....................

.. list-table:: Frozen Delights!
   :widths: 15 10 30
   :header-rows: 1

   * - Treat
     - Quantity
     - Description

   * - Albatross
     - 2.99
     - On a stick!
   * - Crunchy Frog
     - 1.49
     - If we took the bones out, it wouldn't be
       crunchy, now would it?
   * - Gannet Ripple
     - 1.99
     - On a stick!
     

Sourcecode including syntax highlighting
----------------------------------------

.. sourcecode:: python

    class Author(object):
        """Smartly manages a author with name and email"""
        parse_author_regex = re.compile(r'([^<>]*)( +<(.*@.*)>)$')

        def __init__(self, raw='', name=None, email=None):
            self.raw = raw
            self.name = name
            self.email = email

        @classmethod
        def parse(cls, raw):
            a = cls(raw)
            a.name, _, a.email = cls.parse_author_regex.match(raw).groups()

        def __str__(self):
            if not self.name:
                return self.raw
            if not self.email:
                return self.name

            return "{0} <{1}>".format(self.name, self.email)

