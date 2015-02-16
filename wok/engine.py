#!/usr/bin/python2
import os
import sys
import shutil
from datetime import datetime
import time
from optparse import OptionParser, OptionGroup
import logging
import fnmatch

import yaml

import wok
from wok.page import Page, Author
from wok import renderers
from wok import util
from wok.dev_server import dev_server

import locale

class Engine(object):
    """
    The main engine of wok. Upon initialization, it generates a site from the
    source files.
    """
    default_options = {
        'content_dir': 'content',
        'template_dir': 'templates',
        'output_dir': 'output',
        'working_dir': 'output.work',
        'create_backup' : False,
        'media_dir': 'media',
        'site_title': 'Some random Wok site',
        'url_pattern': '/{category}/{slug}{page}.{ext}',
        'url_include_index': True,
        'relative_urls': False,
        'locale': None,
        'markdown_extra_plugins': [],
        'exclude_files': [],
        'rst_doctitle': False,
        'rst_initial_header_level': 1,
        'rst_strip_comments' : True,
        'rst_toc_backlinks' : 'entry',
    }
    SITE_ROOT = os.getcwd()

    def __init__(self, output_lvl=1):
        """
        Set up CLI options, logging levels, and start everything off.
        Afterwards, run a dev server if asked to.
        """

        # CLI options
        # -----------
        parser = OptionParser(version='%prog v{0}'.format(wok.version))

        # Add option to to run the development server after generating pages
        devserver_grp = OptionGroup(parser, "Development server",
                "Runs a small development server after site generation. "
                "--address and --port will be ignored if --server is absent.")
        devserver_grp.add_option('--server', action='store_true',
                dest='runserver',
                help="run a development server after generating the site")
        devserver_grp.add_option('--address', action='store', dest='address',
                help="specify ADDRESS on which to run development server")
        devserver_grp.add_option('--port', action='store', dest='port',
                type='int',
                help="specify PORT on which to run development server")
        parser.add_option_group(devserver_grp)

        # Options for noisiness level and logging
        logging_grp = OptionGroup(parser, "Logging",
                "By default, log messages will be sent to standard out, "
                "and report only errors and warnings.")
        parser.set_defaults(loglevel=logging.WARNING)
        logging_grp.add_option('-q', '--quiet', action='store_const',
                const=logging.ERROR, dest='loglevel',
                help="be completely quiet, log nothing")
        logging_grp.add_option('--warnings', action='store_const',
                const=logging.WARNING, dest='loglevel',
                help="log warnings in addition to errors")
        logging_grp.add_option('-v', '--verbose', action='store_const',
                const=logging.INFO, dest='loglevel',
                help="log ALL the things!")
        logging_grp.add_option('--debug', action='store_const',
                const=logging.DEBUG, dest='loglevel',
                help="log debugging info in addition to warnings and errors")
        logging_grp.add_option('--log', '-l', dest='logfile',
                help="log to the specified LOGFILE instead of standard out")
        parser.add_option_group(logging_grp)

        cli_options, args = parser.parse_args()

        # Set up logging
        # --------------
        logging_options = {
            'format': '%(levelname)s: %(message)s',
            'level': cli_options.loglevel,
        }
        if cli_options.logfile:
            logging_options['filename'] = cli_options.logfile
        else:
            logging_options['stream'] = sys.stdout

        logging.basicConfig(**logging_options)

        self.runserver = cli_options.runserver

        serverrun_flag = ".server_running"

        if os.path.exists(serverrun_flag):
            print ""
            print "Attention: 'wok --server' seems to be running with this directory as source."
            print "           Starting another run or instance isn't a good idea..."
            print ""
            print "           You might want to stop the server (via Ctrl-C in it's window)."
            print ""
            print "           If you are sure that there isn't a server instance running,"
            print "           you should delete file '%s'." % serverrun_flag
            print ""
            sys.exit(1)

        # Action!
        # -------
        self.generate_site()

        # Dev server
        # ----------

        #todo: Bug: on error (e.g. YAML error) no longer the output_dir is served,
        #           but the current dir?!?!?!

        if cli_options.runserver:
            ''' Run the dev server if the user said to, and watch the specified
            directories for changes. The server will regenerate the entire wok
            site if changes are found after every request.
            '''
            output_dir = self.options['working_dir']
            host = '' if cli_options.address is None else cli_options.address
            port = 8000 if cli_options.port is None else cli_options.port
            server = dev_server(serv_dir=output_dir, host=host, port=port,
                dir_mon=True,
                watch_dirs=[
                    self.options['media_dir'],
                    self.options['template_dir'],
                    self.options['content_dir']
                ],
                change_handler=self.generate_site)

            with open(serverrun_flag, "w") as f:
                f.write("")
            server.run()

            # server.run() leaves in output_dir!?
            os.chdir(self.SITE_ROOT)
            try:
                self.vss_remove(serverrun_flag)
            except WindowsError as e:
                pass

        self.handle_output_dir()

        sys.exit(self.error_count)

    def generate_site(self):
        ''' Generate the wok site '''

        self.error_count = 0

        orig_dir = os.getcwd()
        os.chdir(self.SITE_ROOT)

        self.all_pages = []

        self.read_options()
        self.sanity_check()
        self.load_hooks()
        self.renderer_options()

        self.run_hook('site.start')

        self.prepare_output()
        self.error_count += self.load_pages()
        self.make_tree()
        self.error_count += self.render_site()

        self.run_hook('site.done')

        os.chdir(orig_dir)


    def vss_rename(self, src, dest):
        """ virus scanner safe os.rename

        This problem only applies to Windows!

        Some virus scanners (e.g. Avira Antivir) are (badly) locking files during scan
        and therefore prevent a rename of them or the containing directory.
        A Windows error [5] Access denied is raised then.

        One possible workaround is to exclude the problematic directories (here: wok output) from virus scan.

        But a better one might be the one below.
        It tries several times with a little wait inbetween to rename.
        If it doesn't succedd within a few seconds finally an error is raised.
        Usually one wait (1/10 second) is enough.

        References:

        The one with the solution for me:
            http://bytes.com/topic/python/answers/516413-intermittent-permission-denied-errors-when-using-os-rename-recently-deleted-path

        More interesting finding on the way:
            http://stackoverflow.com/questions/3764072/c-win32-how-to-wait-for-a-pending-delete-to-complete
            http://bugs.python.org/issue1425127     os.remove OSError: [Errno 13] Permission denied
            https://groups.google.com/forum/#!topic/comp.lang.python/8uDyIZQVzJ8
            http://mercurial.selenic.com/wiki/UnlinkingFilesOnWindows
            http://mercurial.markmail.org/thread/t5ecar6sn3ekifo6   How Mercurial could be made working with Virus Scanners on Windows
            https://msdn.microsoft.com/en-us/library/aa363858%28VS.85%29.aspx
            http://bz.selenic.com/show_bug.cgi?id=2524  update loses working copy files on Windows for open files
        """

        #print "Trying to rename '%s' to '%s' now" %(src, dest)
        MAX_RETRY_DURATION_s = 3
        startTime = time.clock()
        while True:
            try:
                os.rename(src, dest)
                break
            except OSError as e:
                #print "Error", e, "waiting a bit..."
                if (time.clock() - startTime) > MAX_RETRY_DURATION_s:
                    raise
                else:
                    time.sleep(0.1)

    def vss_remove(self, f):
        """ virus scanner safe os.remove
        """
        #print "Trying to remove '%s' now" %(f)
        MAX_RETRY_DURATION_s = 3
        startTime = time.clock()
        while True:
            try:
                os.remove(f)
                break
            except (OSError, WindowsError) as e:
                #print "Error", e, "waiting a bit..."
                if (time.clock() - startTime) > MAX_RETRY_DURATION_s:
                    raise
                else:
                    time.sleep(0.1)

    def vss_rmtree(self, d):
        """ virus scanner safe shutil.rmtree
        """
        #print "Trying to remove directory tree '%s' now" %(d)
        MAX_RETRY_DURATION_s = 3
        startTime = time.clock()
        while True:
            try:
                shutil.rmtree(d)
                break
            except (WindowsError, OSError) as e:
                #print "Error", e, "waiting a bit..."
                if (time.clock() - startTime) > MAX_RETRY_DURATION_s:
                    raise
                else:
                    time.sleep(0.1)

    def handle_output_dir(self):
        if self.error_count == 0:

            os.chdir(self.SITE_ROOT)
            if os.path.isdir(self.options['output_dir']+'.bak'):
                self.vss_rmtree(self.options['output_dir']+'.bak')
            if os.path.isdir(self.options['output_dir']):
                if self.options['create_backup']:
                    # This rename (the original os.rename()) wasn't a problem,
                    # but using the safe call here too now.
                    self.vss_rename(self.options['output_dir'], self.options['output_dir']+'.bak')
                else:
                    #another tried workaround for the virus scanner problem. Didn't help.
                    #tmpname = self.options['output_dir']+'.del'+ datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
                    #print "Renaming output to", tmpname, " - as bughandling"
                    #os.rename(self.options['output_dir'], tmpname)
                    ##print "and delete it then"
                    ##shutil.rmtree(tmpname)
                    self.vss_rmtree(self.options['output_dir'])

            #if os.path.isdir(self.options['output_dir']):
            #    print self.options['output_dir'], "found"
            #else:
            #    print "NO", self.options['output_dir'], "found"
            #
            #if os.path.isdir(self.options['working_dir']):
            #    print self.options['working_dir'], "found"
            #else:
            #    print "NO", self.options['working_dir'], "found"

            # Here the originally used os.rename() often failed on Windows.
            # See documentation in vss_rename().
            self.vss_rename(self.options['working_dir'], self.options['output_dir'])

        else:
            print ""
            print "Result:"
            print "Due to errors there has no (new) output directory '%s' been created!" % (self.options['output_dir'])
            print "The files are still in '%s' and the last successful run remains in '%s'." % (self.options['working_dir'], self.options['output_dir'])

    def read_options(self):
        """Load options from the config file."""
        self.options = Engine.default_options.copy()

        if os.path.isfile('wokconfig'):
            with open('wokconfig') as f:
                yaml_config = yaml.load(f)

            if yaml_config:
                self.options.update(yaml_config)
        else:
            logging.warn("Deprecation: You are still using the old config file name 'config'."
                         " The preferred new name is 'wokconfig'.")

            if os.path.isfile('config'):
                with open('config') as f:
                    yaml_config = yaml.load(f)

                if yaml_config:
                    self.options.update(yaml_config)

        # Make authors a list, even only a single author was specified.
        authors = self.options.get('authors', self.options.get('author', None))
        if isinstance(authors, list):
            self.options['authors'] = [Author.parse(a) for a in authors]
        elif isinstance(authors, str):
            csv = authors.split(',')
            self.options['authors'] = [Author.parse(a) for a in csv]
            if len(self.options['authors']) > 1:
                logging.warn('Deprecation Warning: Use YAML lists instead of '
                        'CSV for multiple authors. i.e. ["John Doe", "Jane '
                        'Smith"] instead of "John Doe, Jane Smith". In wokconfig '
                        'file.')

        # Make exclude_files a list, even only a single pattern was specified.
        exclude_files = self.options.get('exclude_files', None)
        if isinstance(exclude_files, str):
            self.options['exclude_files'] = [e.strip() for e in exclude_files.split(',')]
            if len(self.options['exclude_files']) > 1:
                logging.warn('Deprecation Warning: Use YAML lists instead of '
                        'CSV for multiple file exclusions. i.e. ["*.ignore", '
                        '"__*"] instead of "*.ignore , __*" in wokconfig file.')

        if '{type}' in self.options['url_pattern']:
            logging.warn('Deprecation Warning: You should use {ext} instead '
                    'of {type} in the url pattern specified in the wokconfig '
                    'file.')

        # Set locale if needed
        wanted_locale = self.options.get('locale')
        if wanted_locale is not None:
            try:
                locale.setlocale(locale.LC_TIME, wanted_locale)
            except locale.Error as err:
                logging.warn('Unable to set locale to `%s`: %s',
                    wanted_locale, err
                )

        # make sure that output_dir is always only a name, not any path!
        outdir = os.path.basename(self.options['output_dir'].strip("./"))
        if outdir != self.options['output_dir']:
            logging.error("Option 'output_dir' must not contain a path (%s), "
                          "only a directory name! Stripped it down to '%s'."
                          % (self.options['output_dir'], outdir))
        self.options['output_dir'] = outdir

        # add a subdir prefix to the output_dir, if present in the config
        self.options['server_root'] = self.options['output_dir']
        if self.options.get('url_subdir', ''):
            self.options['output_dir'] = os.path.join(self.options['output_dir'], self.options['url_subdir'])

    def renderer_options(self):
        """Monkeypatches renderer options as in `wokconfig` file."""
        # Markdown extra plugins
        markdown_extra_plugins = \
            self.options.get('markdown_extra_plugins', [])
        if hasattr(renderers, 'Markdown'):
            renderers.Markdown.plugins.extend(markdown_extra_plugins)
        if hasattr(renderers, 'Markdown2'):
            renderers.Markdown2.extras.extend(markdown_extra_plugins)

        # reStructuredText options
        if hasattr(renderers, 'ReStructuredText'):
            renderers.ReStructuredText.options.update( \
                {'doctitle' : self.options.get('rst_doctitle', False), \
                 'initial_header_level' : self.options.get('rst_initial_header_level', 1),
                 'strip_comments' : self.options.get('rst_strip_comments', True),
                 'toc_backlinks' : self.options.get('rst_toc_backlinks', 'entry'),
                })

    def sanity_check(self):
        """Basic sanity checks."""
        # Make sure that this is (probabably) a wok source directory.
        if not (os.path.isdir('templates') or os.path.isdir('content')):
            logging.critical("This doesn't look like a wok site. Aborting.")
            sys.exit(1)

    def load_hooks(self):
        try:
            sys.path.append('hooks')
            import __hooks__
            self.hooks = __hooks__.hooks
            logging.info('Loaded {0} hooks: {0}'.format(self.hooks))
        except ImportError as e:
            if "__hooks__" in str(e):
                logging.info('No hooks module found.')
            else:
                # don't catch import errors raised within a hook
                logging.info('Import error within hooks.')
                raise

    def run_hook(self, hook_name, *args):
        """ Run specified hooks if they exist """
        logging.debug('Running hook {0}'.format(hook_name))
        returns = []
        try:
            for hook in self.hooks.get(hook_name, []):
                returns.append(hook(self.options, *args))
        except AttributeError:
            logging.info('Hook {0} not defined'.format(hook_name))
        return returns

    def prepare_output(self):
        """
        Prepare the output/working directory. Remove any contents there already, and
        then copy over the media files, if they exist.
        """

        output_dir = self.options['working_dir']

        if os.path.isdir(output_dir):
            for name in os.listdir(output_dir):
                # Don't remove dotfiles              #todo: why? What about copying from output_dir?
                if name[0] == ".":
                    continue
                path = os.path.join(output_dir, name)
                if os.path.isfile(path):
                    os.unlink(path)
                else:
                    shutil.rmtree(path)
        else:
            os.makedirs(output_dir)

        self.run_hook('site.output.pre', output_dir)

        # Copy the media directory to the output folder
        if os.path.isdir(self.options['media_dir']):
            try:
                for name in os.listdir(self.options['media_dir']):
                    path = os.path.join(self.options['media_dir'], name)
                    if os.path.isdir(path):
                        shutil.copytree(
                                path,
                                os.path.join(output_dir, name),
                                symlinks=True
                        )
                    else:
                        shutil.copy(path, output_dir)


            # Do nothing if the media directory doesn't exist
            except OSError:
                logging.warning('There was a problem copying the media files '
                                'to the output directory.')

            self.run_hook('site.output.post', output_dir)

    def load_pages(self):
        """Load all the content files."""

        error_count = 0

        # Load pages from hooks (pre)
        for pages in self.run_hook('site.content.gather.pre'):
            if pages:
                self.all_pages.extend(pages)

        # Load files
        for root, dirs, files in os.walk(self.options['content_dir']):
            # Grab all the parsable files
            for f in files:
                # Don't parse hidden files.
                if f.startswith('.'):
                    continue

                # Don't parse excluded files.
                if self.options['exclude_files']:
                    exclude_it = False
                    for exf in self.options['exclude_files']:
                        if fnmatch.fnmatch(f, exf):
                            logging.info('File ignored due to user exclusion: {0}'.format(f))
                            exclude_it = True
                            break
                    if exclude_it:
                        continue

                ext = f.split('.')[-1]
                renderer = renderers.Plain

                for r in renderers.all:
                    if ext in r.extensions:
                        renderer = r
                        break
                else:
                    logging.warning('No parser found '
                            'for {0}. Using default renderer.'.format(f))
                    renderer = renderers.Renderer

                p = Page.from_file(os.path.join(root, f), self.options, self, renderer)

                if p and p.errorlog:
                    error_count += 1
                    print "ERRORS in", p.filename
                    for line in p.errorlog:
                        print "   ", line
                    print
                    p.errorlog = []  # clear for next stage!

                if p and p.meta['published']:
                    self.all_pages.append(p)

        # Load pages from hooks (post)
        for pages in self.run_hook('site.content.gather.post', self.all_pages):
            if pages:
                self.all_pages.extend(pages)

        return error_count

    def make_tree(self):
        """
        Make the category pseudo-tree.

        In this structure, each node is a page. Pages with sub pages are
        interior nodes, and leaf nodes have no sub pages. It is not truly a
        tree, because the root node doesn't exist.
        """
        self.categories = {}
        site_tree = []
        # We want to parse these in a approximately breadth first order
        self.all_pages.sort(key=lambda p: len(p.meta['category']))

        # For every page
        for p in self.all_pages:
            # If it has a category (ie: is not at top level)
            if len(p.meta['category']) > 0:
                top_cat = p.meta['category'][0]
                if not top_cat in self.categories:
                    self.categories[top_cat] = []

                self.categories[top_cat].append(p.meta)

            try:
                # Put this page's meta in the right place in site_tree.
                siblings = site_tree
                for cat in p.meta['category']:
                    # This line will fail if the page is an orphan
                    parent = [subpage for subpage in siblings
                                 if subpage['slug'] == cat][0]
                    siblings = parent['subpages']
                siblings.append(p.meta)
            except IndexError:
                logging.error('It looks like the page "{0}" is an orphan! '
                        'This will probably cause problems.'.format(p.path))

    def render_site(self):
        """Render every page and write the output files."""
        error_count = 0
        logging.info("****************** render_site")
        # Gather tags
        tag_set = set()
        for p in self.all_pages:
            tag_set = tag_set.union(p.meta['tags'])
        tag_dict = dict()
        for tag in tag_set:
            # Add all pages with the current tag to the tag dict
            tag_dict[tag] = [p.meta for p in self.all_pages
                                if tag in p.meta['tags']]

        # Gather slugs
        slug_dict = dict((p.meta['slug'], p.meta) for p in self.all_pages)

        for p in self.all_pages:
            # Construct this every time, to avoid sharing one instance
            # between page objects.
            templ_vars = {
                'site': {
                    'title': self.options.get('site_title', 'Untitled'),
                    'datetime': datetime.now(),
                    'date': datetime.now().date(),
                    'time': datetime.now().time(),
                    'tags': tag_dict,
                    'pages': self.all_pages[:],
                    'categories': self.categories,
                    'slugs': slug_dict,
                },
            }

            for k, v in self.options.iteritems():
                if k not in ('site_title', 'output_dir', 'content_dir',
                        'working_dir', 'create_backup', 'templates_dir',
                        'media_dir', 'url_pattern'):

                    templ_vars['site'][k] = v

            if 'author' in self.options:
                templ_vars['site']['author'] = self.options['author']

            if self.runserver:
                templ_vars['site']['base'] = '<base href="">'
            else:
                templ_vars['site']['base'] = '<base href="%s">' % self.options.get("base", "")

            # Rendering the page might give us back more pages to render.
            new_pages = p.render(templ_vars)

            if p and p.errorlog:
                error_count += 1
                print "ERRORS while working on", p.filename
                for line in p.errorlog:
                    print "   ", line
                p.errorlog = []     # just cleanup

            if p.meta['make_file']:
                p.write()

            if new_pages:
                logging.debug('found new_pages')
                self.all_pages += new_pages

        return error_count

if __name__ == '__main__':
    Engine()
    exit(0)
