# Todo list for hyde diverator plugin 

## Must have's before submitting pull request

* abstract so it can be used in any situation beyond impress.js
* build generic example as index.html
* make the filter act as a jinja tag

    I want to use it like: {% diverate %}{% end diverate %}

* allow variable length separators. I am considering:

    1. `=+-+=+`
    2. `\-+\`
    3. `[-+` or other bracket similarities (currently I prefer this idea)

* allow strings at the start seperator:

    so you can write `[------- title for readability [[[1`, which can
    also be used for building folds and such in vim and other text
    editors. It might also be interesting to use this title. Maybe it
    can be a comment or header `<!-- title for readability -->` or
    `<h1>title for readability</h1>`. I currently prefer a comment

* Add comments to the relevant site.yaml configs
* allow config
* switch to context filter instead of environment so that it can check
  `resource.meta` for relevant configurations
* Allow setting to control class or id enumeration

    This can work like a config `enumerated_id: "div-%d"` and then later used
    as `enumerated_id % slide_idx`

## Things to consider, but not necessary

* consider changing "Slide" name to something more generic, but slide is
  not bad
* consider seperating yaml front matter by only the bottom `---` instead
  of a cage. This way you have N less lines in your text file for N slides/divs.
  One catch: take care to make sure that markdown horizontal rule are not mistakenly
  taken for the yaml-front-matter ending.



