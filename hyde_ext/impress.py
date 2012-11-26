from hyde.model import Expando
from hyde.plugin import Plugin

from jinja2 import environmentfilter, Environment

from operator import attrgetter
import re
import yaml


'''

ImpressPlugin allows the generation of impress.js presentations
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

RE_SLIDE = re.compile(r'(?<=^==--==\n)(.*\n)+?(?=^==--==$)', re.MULTILINE)
RE_YAML  = re.compile(r'(?<=^---\n)(.*\n)+?(?=^---$)', re.MULTILINE)
RE_NOT_YAML  = re.compile(r'[^-]', re.MULTILINE)

class Slide(Expando):
    '''
    A convenient class that represents a slide in impres.js.
    It takes in the whole text of the slide and produces
    an html div element for impress to work with.
    '''
    def __init__(self, text):
        self.raw = text
        self._parse_meta()
        self._parse_text()
        self._gen_html()

    def _parse_meta(self):
        try:
            meta = RE_YAML.search(self.raw).group(0)
        except AttributeError:
            meta = "class: step"

        ym = yaml.load(meta)

        # then add the step class if necessary which
        # signals a single slide in impress.js
        try:
            if "step" not in ym["class"]:
                ym["class"] += " step"
        except KeyError:
            ym["class"] = "step"

        # create the meta data for the div element
        self.meta = ""
        for name, value in ym.items():
            self.meta += " %s='%s'" % (name, value)

    def _parse_text(self):
        # find the yaml front matter
        idx_yaml_start = self.raw.find("---\n")
        idx_yaml_end   = self.raw.find("---\n",idx_yaml_start+3)
        self.text = self.raw[idx_yaml_end+3:]

    def _gen_html(self):
        self.start = "<div%s>" % self.meta
        self.end   = "</div>"

def get_impress(env, default_filter):

    # grab the default filter from the template
    try:
        f = env.filters[default_filter]
    except AttributeError:
        f = None

    @environmentfilter
    def impress_filter(env, text, filt=f):
        html = ""

        for s_text in RE_SLIDE.finditer(text):
            s = Slide(s_text.group(0))

            try:
                t = filt(env, s.text)
            except TypeError:
                t = s.text

            html += '''
%s
%s
%s
            ''' % (s.start, t, s.end)

        return html
    return impress_filter

    #return "\n\n".join(result)


class ImpressPlugin(Plugin):
    '''
    '''
    def __init__(self, site):
        super(ImpressPlugin, self).__init__(site)

    def _parse_impress_config(self):
        '''
        Attempt to set the parameters for Impress
        based on the site config file
        '''
        config = self.site.config
        for name, value in config.impress.__dict__.items():
            setattr(self, name, value)

    def template_loaded(self,template):
        super(ImpressPlugin, self).template_loaded(template)

        self._parse_impress_config()

        env = self.template.env

        # define the custom filter
        impress = get_impress(env, self.filter)

        # give the impress filter up to hyde
        self.template.env.filters.update({'impress' : impress })

