title: ReST Title test with lonely leading H1
category: tests
# The following option turns on the rst behaviour up to wok 1.1.1
# but only for this document. The global default is 'false' as of 1.1.2c
# See text below H1
rst_doctitle: true
---

=============
This is an h1
=============

| The  H1 above "This is an h1" doesn't appear in output because it's lonely and at begin of file.
| reStructuredText treats it as document title instead...

From wok version 1.1.2c on that behaviour is disabled by default.

Text of an h1

-------------
This is an h2
-------------
Text of an h2


----------
Another h2
----------
Text in an h2

~~~~~~~~~~~~~
This is an h3
~~~~~~~~~~~~~
Text in an h3

an h4
=====
text in an h4

an h5
-----
text in an h5

an h6
~~~~~
text in an h6

This is text
