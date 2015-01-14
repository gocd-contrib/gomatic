# Change log

*Note* - this describes breaking API changes only, not additions to the API unless they are particularly important.

## 0.3.0

* artifacts are now a set rather than a list
* `GoServerConfigurator` has been renamed `GoCdConfigurator` - slightly shorter.

## 0.2.0

* `GoServer` has been renamed `GoServerConfigurator` for clarity.

## 0.1.1

* `Pipeline.set_git_url` now only takes url parameter. For other Git options, use `Pipeline.set_git_material(GitMaterial(...))`.
