import logging
from wok import util

# Check for pygments
try:
    import pygments
    have_pygments = True
except ImportError:
    logging.warn('Pygments not enabled.')
    have_pygments = False

# List of available renderers
all = []

class Renderer(object):
    extensions = []

    @classmethod
    def render(cls, plain):
        return plain
all.append(Renderer)

class Raw(Renderer):
    """Same as the default Renderer. For explicitely raw files."""
    extensions = ['raw']
all.append(Raw)

class Plain(Renderer):
    """Plain text renderer. Replaces new lines with html </br>s"""
    extensions = ['txt']

    @classmethod
    def render(cls, plain):
        return plain.replace('\n', '<br>')
all.append(Plain)

# Include markdown, if it is available.
try:
    from markdown import markdown

    class Markdown(Renderer):
        """Markdown renderer."""
        extensions = ['markdown', 'mkd', 'md']

        plugins = ['def_list', 'footnotes']
        if have_pygments:
            plugins.extend(['codehilite(css_class=codehilite)', 'fenced_code'])

        @classmethod
        def render(cls, plain):
            return markdown(plain, cls.plugins)

    all.append(Markdown)

except ImportError:
    logging.warn("markdown isn't available, trying markdown2")
    markdown = None

# Try Markdown2
if markdown is None:
    try:
        import markdown2
        class Markdown2(Renderer):
            """Markdown2 renderer."""
            extensions = ['markdown', 'mkd', 'md']

            extras = ['def_list', 'footnotes']
            if have_pygments:
                extras.append('fenced-code-blocks')

            @classmethod
            def render(cls, plain):
                return markdown2.markdown(plain, extras=cls.extras)

        all.append(Markdown2)
    except ImportError:
        logging.warn('Markdown not enabled.')


# Include ReStructuredText Parser, if we have docutils
try:
    import docutils.core
    from docutils.writers.html4css1 import Writer as rst_html_writer
    from docutils.parsers.rst import directives

    if have_pygments:
        from wok.rst_pygments import Pygments as RST_Pygments
        directives.register_directive('Pygments', RST_Pygments)

    class ReStructuredText(Renderer):
        """reStructuredText renderer."""
        extensions = ['rst']

        @classmethod
        def render(cls, plain):
            w = rst_html_writer()
            #return docutils.core.publish_parts(plain, writer=w)['body']       # original, but missing heading and/or title if it's a lone heading

            # Workarounds and investigation:
            #
            # see: http://docutils.sourceforge.net/docs/api/publisher.html#publish-parts-details
            #
            #return docutils.core.publish_parts(plain, writer=w)['whole']      # complete, just for testing
            #return docutils.core.publish_parts(plain, writer=w)['body_pre_docinfo'] + \
            #       docutils.core.publish_parts(plain, writer=w)['body']       # really good, but missing the id of title div. If that's important...
            #return docutils.core.publish_parts(plain, writer=w)['html_body']  # better, but might contain too much. E.g. a surrounding div.
            #                                                                  # Need to be tested...
            #
            ## still the above workarounds have a "wrong" heading hierarchy as described here:
            #
            #      http://docutils.sourceforge.net/FAQ.html#unexpected-results-from-tools-rst2html-py-h1-h1-instead-of-h1-h2-why

            # Solution:
            #     Disable the promotion of a lone top-level section title to document title
            #     (and subsequent section title to document subtitle promotion)
            #
            #      http://docutils.sourceforge.net/docs/api/publisher.html#id3
            #      http://docutils.sourceforge.net/docs/user/config.html#doctitle-xform
            #
            overrides = {'doctitle_xform': False}
            return docutils.core.publish_parts(plain, writer=w, settings_overrides=overrides)['body']

    all.append(ReStructuredText)
except ImportError:
    logging.warn('reStructuredText not enabled.')


# Try Textile
try:
    import textile
    class Textile(Renderer):
        """Textile renderer."""
        extensions = ['textile']

        @classmethod
        def render(cls, plain):
            return textile.textile(plain)

    all.append(Textile)
except ImportError:
    logging.warn('Textile not enabled.')


if len(all) <= 3:
    logging.error("You probably want to install either a Markdown library (one of "
          "'Markdown', or 'markdown2'), 'docutils' (for reStructuredText), or "
          "'textile'. Otherwise only plain text input (and raw input) will be"
          "supported. You can install any of these with 'sudo pip install PACKAGE'.")
