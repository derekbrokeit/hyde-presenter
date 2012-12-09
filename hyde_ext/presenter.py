# -*- coding: utf-8 -*-

from hyde.model import Expando
from hyde.plugin import TextyPlugin

from jinja2 import environmentfilter, nodes
from jinja2.ext import Extension

import re
import yaml

import sys

'''

PresenterPlugin allows the generation of complex html structures in
easy to read files. This allows you to quickly host stunning, dynamic
presentation on the web. With the ability to write very simple layouts
and automatically generate the html markup makes this plugin incredibly
powerful.

The structures in presenter are two fold: 1) Presentation and 2) slides.
The idea si that presentations are the enclosing html element with
slides sequentially layed out afterward. This can make anything form
slideshows, headers, and even impress.js presentations with ease.

As an example, the following is a two-slide layout:

∂∂ my-presentation
………………
This is a slide
this is still on the first slide

………………
# yaml matter goes here
id: test
class: foo
---
slide **two** text
………………
∂∂ /my-presentation

As you can see, a presentation is enclosed in '∂∂' blocks with an
id-tag 'my-presentation' (whatever you want). Each slide can have it's
meta data specified in a yaml-header. Meta data takes the form of tag
properties 'class="foo" id="test"'. This can be set in the resource meta
data or in the sites.yaml configurations under 'presenter'.

You can also add slide enumeration to class and id attributes by setting
the meta value to include '%d' for the slide-id-number. After the
presentation has been processed, it can be retrieved and used in the
`resource.pres` list. A resource can have as many presentations as
desired.

Note: For impress.js presentations, every slide should have a "step"
class and the presentation id should be "impress".

'''

PROP        = u"%s='%s'"
START_TAG   = u"<%s%s>"
END_TAG     = u"</%s>"
COMMENT_TAG = "<!-- %s -->\n"
ELEMENT     = "%s\n%s\n%s"

YAML_FINDER = "---"

FENCE_CHAR = u'…'
FENCE_REP  = 5
SLIDE_RE = re.compile( \
        ur'(?P<fence>^(?:%s{%d,}))(?:%s*)[ ]*(\{?\.?(?P<comment>[a-zA-Z0-9_-]*)\}?)?[ ]*\n(?P<slide>.*?)(?<=\n)(?P=fence)' % (FENCE_CHAR, FENCE_REP, FENCE_CHAR),
    #ur'(?P<fence>^(?:…{5,}))[ ]*(\{?\.?(?P<comment>[a-zA-Z0-9_-]*)\}?)?[ ]*\n(?P<slide>.*?)(?<=\n)(?P=fence)[ ]*$',
    re.UNICODE|re.MULTILINE|re.DOTALL
    )



config_cache = {}
default = {
                "element":  "div", # element of the outer presentation
                "meta":    None,   # class of the outer presentation
                }
slide_default = {
                "filter" :  None,  # filter used on each individual slide
                "element":  "div", # element of individual slides
                "meta": None,
            }


class HTMLStructure(Expando):
    '''
    A structure that represents an html element with a start-tag and end-tag with
    text between the tags. The properties of this structure are held in the meta-attribute.
    '''
    def __init__(self, raw_text, element, meta=None):
        self.raw_text = raw_text
        self.element  = element
        if meta:
            self.meta     = Expando(meta)
        else:
            self.meta = Expando({})

    @property
    def props(self):
        props = ""
        for key_val in self.meta.__dict__.items():
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
    '''
    A Presentation structure holds a series of slides for presentation
    '''
    def __init__(self, raw_text, element, meta, slide_items):

        super(Presentation, self).__init__(raw_text, element, meta)

        self.slide_items = slide_items
        self.slides = []
        self._generate_slides()

    def _generate_slides(self):
        '''
        build the slides list
        '''

        i = 0
        text = self.raw_text
        while True:
            s =  SLIDE_RE.search(text)
            if s:
                comment = s.group('comment')
                if comment:
                    comment = COMMENT_TAG % comment
                slide_text = s.group('slide')

                self.slides.append(
                        Slide(slide_text, idx=i, comment=comment, **self.slide_items)
                        )
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
    A repsresentation of a slide to present a small snippet of text or html
    '''
    def __init__(self, raw_text, element, meta, idx, env, filter=None, comment=None):
        super(Slide, self).__init__(raw_text, element, meta)

        self.env     = env
        self.filter  = filter
        self.idx     = idx
        self.comment = comment

        self._parse_raw_text()

    def _parse_raw_text(self):
        '''
        find the meta data and text
        '''
        # first, find yaml matter,
        # assuming only the bottom '---' to save space
        idx_ym = self.raw_text.find(YAML_FINDER, len(YAML_FINDER))
        if idx_ym > 0:
            ym = self.raw_text[:idx_ym-1]
        else:
            ym = ''

        # make the meta dict
        meta = Expando(yaml.load(ym))
        if not meta:
            # if meta is None, make is a dict
            meta = Expando({})
        elif isinstance(self.meta, str):
            # if meta ends up as a string, assume it's empty
            meta = Expando({})
            idx_ym = -1

        # if a meta collision occurs, the yaml-matter is prefered
        # except in the case of 'class', which appends it to the existing version
        try:
            old_class = getattr(self.meta, "class")
            new_class = old_class + " " + getattr(meta, "class")
            setattr(self.meta, "class", new_class)
            delattr(meta, "class")
        except AttributeError:
            pass
        self.meta.update(meta)

        # attempt to enumerate class and id, if possible
        try:
            setattr(self.meta, "id", self.meta.id % self.idx)
        except (AttributeError, TypeError):
            pass
        try:
            setattr(self.meta, "class", getattr(self.meta, "class") % self.idx)
        except (AttributeError, TypeError):
            pass

        # now find the standard text
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
def presenter(env, raw_text, id=None, resource=None):
    '''
    A filter that builds a presentation
    '''
    # get the config data relevant to this presentation's settings
    try:
        res_meta = getattr(resource.meta, "presenter")
    except AttributeError:
        res_meta = None
    try:
        res_meta_id = getattr(res_meta, id)
    except AttributeError:
        res_meta_id = None
    try:
        conf_id = getattr(config_cache, id)
    except AttributeError:
        conf_id = None

    # gather relevant settings for the presentation and slides
    settings = {
            "raw_text": raw_text,
            "slide_items": {
                "env": env
                }
            }
    # look for the proper settings for the presentation
    for k,v in default.items():
        try:
            # try resource.meta.presenter.KEY
            settings[k] = getattr(res_meta, k)
        except AttributeError:
            try:
                # try resource.meta.presenter.ID.KEY
                settings[k] = getattr(res_meta_id, k)
            except AttributeError:
                try:
                    # try config.presenter.ID.KEY
                    settings[k] = getattr(conf_id, k)
                except AttributeError:
                    # take the default value
                    settings[k] = v
    # set the id meta data
    if id:
        if settings["meta"]:
            settings["meta"].update({"id": id})
        else:
            settings["meta"] = Expando({"id": id})
    # look for the proper settings for the slides
    for k,v in slide_default.items():
        try:
            # try resource.meta.presenter.slides.KEY
            settings["slide_items"][k] = getattr(getattr(res_meta,"slides"), k)
        except AttributeError:
            try:
                # try resource.meta.presenter.slides.ID.KEY
                settings["slide_items"][k] = getattr(getattr(res_meta_id,"slides"), k)
            except AttributeError:
                try:
                    # try config.presenter.slides.ID.KEY
                    settings["slide_items"][k] = getattr(getattr(conf_id,"slides"), k)
                except AttributeError:
                    # take the default value
                    settings["slide_items"][k] = v

    # get the resource's presentation list
    try:
        pres = resource.pres
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

    def _render_presenter(self, id=None, resource=None, caller=None):
        """
        Calls the presenter filter to transform the output.
        """
        if not caller:
            return ''
        output = caller().strip()
        return presenter(self.environment, output, id, resource)


class PresenterPlugin(TextyPlugin):
    '''
    A hyde plugin to aid in the creation of easy to present html-structures and
    helper for the Presenter Jinja2 extension
    '''
    def __init__(self, site):
        super(PresenterPlugin, self).__init__(site)

    def _cache_config(self):
        '''
        caches the site configs for this plugin so that the jinja extension
        can access them
        '''
        global config_cache, default, slide_default
        config = self.site.config
        config_cache = config.presenter
        try:
            d = config_cache.default.__dict__
            try:
                s = d["slides"].__dict__
                del d["slides"]
            except KeyError:
                s = None
        except AttributeError:
            d = None
        if d:
            # change the default settings
            for k, v in d.items():
                default[k] = v
            if s:
                # change the default settings for slides
                for k, v in s.items():
                    slide_default[k] = v

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

