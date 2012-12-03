# -*- coding: utf-8 -*-

from hyde.model import Expando
from hyde.plugin import TextyPlugin

from jinja2 import environmentfilter, nodes
from jinja2.ext import Extension

import re
import yaml

import sys

'''

PresenterPlugin allows the generation of impress.js presentations
on the fly from text files. This allows you to host stunning, dynamic
presentation on the web.

Slides are encased in dumbbell blocks '==--=='. Each slide can have
custom meta data added to the step element in a slide specific
yaml-front-matter. Customized default filters can be applied to the
slides from the sites.yaml configuration settings. No customization
means no filter is applied.

Example two slide layout:

==--==
This is a slide
this is still on the first slide

==--==
---
# yaml matter goes here
id: test
---
slide **two** text
==--==
'''

PROP        = u"%s='%s'"
START_TAG   = u"<%s%s>"
END_TAG     = u"</%s>"
COMMENT_TAG = "<!-- %s -->\n"
ELEMENT     = "%s\n%s\n%s"

YAML_FINDER = "---"

#RE_SLIDE = re.compile(r'(?<=^==--==\n)(.*\n)+?(?=^==--==$)', re.MULTILINE)
#RE_YAML  = re.compile(r'(?<=^---\n)(.*\n)+?(?=^---$)', re.MULTILINE)

FENCE_CHAR = u'…'
FENCE_REP  = 5
SLIDE_RE = re.compile( \
        ur'(?P<fence>^(?:%s{%d,}))(?:…*)[ ]*(\{?\.?(?P<comment>[a-zA-Z0-9_-]*)\}?)?[ ]*\n(?P<slide>.*?)(?<=\n)(?P=fence)' % (FENCE_CHAR, FENCE_REP),
    #ur'(?P<fence>^(?:…{5,}))[ ]*(\{?\.?(?P<comment>[a-zA-Z0-9_-]*)\}?)?[ ]*\n(?P<slide>.*?)(?<=\n)(?P=fence)[ ]*$',
    re.UNICODE|re.MULTILINE|re.DOTALL
    )



config_cache = {}
defaults = {    "element":         "div",
                "outer_element" :  "div",
                "filter" :         None,
                "id_N" :           None,
                "class_N":         None,
            }

class HTMLStructure(Expando):
    '''
    A structure that represents an html element with a start-tag and end-tag with
    text between the tags.
    '''
    def __init__(self, env, raw_text, filter, element, id_N, class_N, meta=None):
        self.env = env
        self.raw_text = raw_text
        self.filter = filter
        self.element = element
        self.id_N = id_N
        self.class_N = class_N
        self.meta = meta

    @property
    def props(self):
        props = ""
        for key_val in self.meta.items():
            props += " " + PROP % key_val

        return props

    @property
    def start_tag(self):
        return START_TAG % (self.element, self.props)

    @property
    def end_tag(self):
        return END_TAG % self.element

    @property
    def text(self):
        return self.raw_text

    @property
    def html(self):
        return ELEMENT % (self.start_tag, self.text, self.end_tag)


class Presentation(HTMLStructure):
    def __init__(self, outer_element=None, **kwargs):
        super(Presentation, self).__init__(**kwargs)

        self.inner_element = self.element
        self.element = outer_element
        self.slides = []
        self._generate_slides()

    def _generate_slides(self):

        i = 0
        text = self.raw_text
        is_impress = (id == "impress") # take precautions to check if this is for impress.js
        general_input = {"is_impress":is_impress, "element":self.inner_element,
                "id_N":self.id_N, "class_N":self.class_N, "filter":self.filter,
                "env": self.env}
        while True:
            s =  SLIDE_RE.search(text)
            if s:
                comment = s.group('comment')
                if comment:
                    comment = COMMENT_TAG % comment
                slide_text = s.group('slide')

                self.slides.append(Slide(idx=i, comment=comment,
                    raw_text=slide_text, **general_input))

            else:
                break

            text = text[s.end()-FENCE_REP:]
            i += 1
        pass

    @property
    def text(self):
        text = ""
        for i,s in enumerate(self.slides):
            if i > 0:
                text += "\n"
            text += "%s" % s.html

        return text


class Slide(HTMLStructure):
    '''
    A convenient class that represents a slide in impres.js.
    It takes in the whole text of the slide and produces
    an html div element for impress to work with.
    '''
    def __init__(self, idx, comment=None, is_impress=False, **kwargs):
        super(Slide, self).__init__(**kwargs)

        self.idx        = idx
        self.comment    = comment
        self.is_impress = is_impress

        self._parse_raw_text()


    def _parse_raw_text(self):
        # first, find yaml matter,
        # assuming only the bottom '---' to save space
        idx_ym = self.raw_text.find(YAML_FINDER, len(YAML_FINDER))
        if idx_ym > 0:
            ym = self.raw_text[:idx_ym-1]
        elif self.is_impress:
            ym = "class: step"
        else:
            ym = ''

        # make the meta dict
        self.meta = yaml.load(ym)
        if not self.meta:
            # if meta is None, make is a dict
            self.meta = {}
        elif isinstance(self.meta, str):
            # if meta ends up as a string, assume it's empty
            self.meta = {}
            idx_ym = -1

        # then add the step class if necessary which
        # signals a single slide in impress.js
        if self.is_impress:
            try:
                if "step" not in self.meta["class"]:
                    self.meta["class"] += " step"
            except KeyError:
                self.meta["class"] = "step"

        try:
            # override the element
            self.element = self.meta["element"]
            del self.meta["element"]
        except KeyError:
            pass

        try:
            # override filter
            self.filter = self.meta["filter"]
            del self.meta["filter"]
        except KeyError:
            pass

        if self.id_N:
            self.meta["id_N"] = self.id_N % self.idx

        if self.class_N:
            try:
                self.meta["class"] += " " + self.class_N % self.idx
            except KeyError:
                self.meta["class"] = self.class_N % self.idx

        # now find the standard text and filter it
        if idx_ym > 0:
            self.slide_text = self.raw_text[idx_ym+len(YAML_FINDER):]
        else:
            self.slide_text = self.raw_text

    @property
    def text(self):
        text = ""
        if self.comment:
            text += self.comment

        # grab the actual filter object, not just the name
        try:
            filter = self.env.filters[self.filter]
        except AttributeError:
            filter = None

        if filter:
            text += filter(self.env, self.slide_text)
        else:
            text += self.slide_text

        return text

@environmentfilter
def presenter(env, raw_text, id=None, classes=None, resource=None):

    # create the presentations meta data
    meta = {}
    if  id:
        meta["id"] = id
    if classes:
        meta["class"] = classes

    settings = {"meta": meta}
    # build up the list of keyword arguments to build a presentation
    # Setting preference starts at the resource, then sites.yaml, then
    # the 'defaults' dict. Actually, element and filter can even be set
    # per element in the element-yaml-matter
    for k in defaults.keys():
        try:
            settings[k] = getattr(resource.meta, k)
        except AttributeError:
            try:
                settings[k] = getattr(config_cache, k)
            except AttributeError:
                settings[k] = defaults[k]

    # add environment and raw text to the settings
    settings["env"] = env
    settings["raw_text"] = raw_text

    # get the resource's presentation list
    try:
        pres = resource.presentations
    except AttributeError:
        resource.pres = []
        pres = resource.pres

    # create a presentation for this resource
    P = Presentation(**settings)
    pres.append(P)

    return P.html

class Presenter(Extension):
    """
    A wrapper around the presenter filter for syntactic sugar.
    """
    tags = set(['presenter'])

    def parse(self, parser):
        """
        Parses the statements and defers to the callback for presenter processing
        """
        lineno = parser.stream.next().lineno

        # now we parse a single expression that is used as cache key.
        args = [parser.parse_expression()]

        # if there is a comma, the user provided a timeout.  If not use
        # None as second parameter.
        if parser.stream.skip_if('comma'):
            args.append(parser.parse_expression())
        else:
            args.append(nodes.Const(None))

        # end tag
        body = parser.parse_statements(['name:endpresenter'], drop_needle=True)

        # add the current resource to the list of args
        args.append(nodes.Name("resource","load"))
        if hasattr(args[0], "name"):
            # correct the id to the Const type
            # used when "∂∂ id-name" is how it is used
            args[0] = nodes.Const(args[0].name)

        return nodes.CallBlock(
                    self.call_method('_render_presenter',args),
                        [], [], body).set_lineno(lineno)

    def _render_presenter(self, id=None, classes=None, resource=None, caller=None):
        """
        Calls the presenter filter to transform the output.
        """
        if not caller:
            return ''
        output = caller().strip()
        return presenter(self.environment, output, id, classes, resource)


class PresenterPlugin(TextyPlugin):
    '''
    '''
    def __init__(self, site):
        super(PresenterPlugin, self).__init__(site)

    def _cache_config(self):
        '''
        caches the site configs for this plugin so that the jinja extension
        can access them
        '''
        global config_cache
        config = self.site.config
        config_cache = config.presenter

    def template_loaded(self,template):
        '''
        once the template is loaded, make sure to cache
        the site configs and then add the extension to our jinja
        template
        '''
        super(PresenterPlugin, self).template_loaded(template)
        self._cache_config()

        # this is what adds the jinja tag {%presenter%}{%endpresenter%}
        self.template.env.add_extension(Presenter)

    @property
    def tag_name(self):
        """
        The mark tag.
        """
        return 'presenter'

    @property
    def default_open_pattern(self):
        """
        The default pattern for presenter open text.
        """
        return u'^∂∂+\s*([A-Za-z0-9_\-]+)\s*$'

    @property
    def default_close_pattern(self):
        """
        The default pattern for mark close text.
        """
        return u'^∂∂+\s*/([A-Za-z0-9_\-]*)\s*$'

    def text_to_tag(self, match, start=True):
        """
        Replace open pattern (default:∂∂ impress)
        with
        {% presenter CSS %} or equivalent and
        Replace close pattern (default: ∂∂ /impress)
        with
        {% endpresenter %} or equivalent
        """
        return super(PresenterPlugin, self).text_to_tag(match, start)

