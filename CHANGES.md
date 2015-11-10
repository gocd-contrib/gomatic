# Change log

*Note* - this describes breaking API changes only, not additions to the API unless they are particularly important.

## 0.4.0

* Many functions have been converted into properties where appropriate.
* Code has been reorganised, if you have `from gomatic.go_cd_configurator import ...` statements in your code, please be
  aware that classes, functions and constants may have moved.
* Tests are now in the special `tests` module. Please see the README for how to run them.
* Where there were functions masquerading as classes, alternate constructors are being provided. The old
  functions-that-look-like-classes are being preserved for now, but it is highly recommended the alternate constructors
  are used for new code where available.
* Please expect class hierarchies to change in upcoming releases.

## 0.3.0

* artifacts are now a set rather than a list
* `GoServerConfigurator` has been renamed `GoCdConfigurator` - slightly shorter.

## 0.2.0

* `GoServer` has been renamed `GoServerConfigurator` for clarity.

## 0.1.1

* `Pipeline.set_git_url` now only takes url parameter. For other Git options, use `Pipeline.set_git_material(GitMaterial(...))`.
