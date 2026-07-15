# Third-Party Notices

The `optiprofiler-solar` distribution combines independently licensed
components. Its distribution license metadata is recorded conservatively as:

`BSD-3-Clause AND LGPL-2.1-only AND LGPL-3.0-or-later`

## OptiProfiler adapter

The Python wrapper, plugin integration, generated metadata, maintenance
scripts, and wrapper documentation are licensed under the BSD 3-Clause License
in `LICENSE`.

## SOLAR runtime source

The slim runtime is derived from
[bbopt/solar](https://github.com/bbopt/solar) at commit
`dda8fd7f98d4392aa07b3e3056888624a00712a0`. The precise source and license
mapping is also recorded in `runtime/solar/manifest.json`.

- Every distributed `runtime/solar/src/*.cpp` and `*.hpp` file carries an
  explicit upstream notice granting use under LGPL-3.0-or-later. Those notices
  are preserved without modification.
- `runtime/solar/src/makefile` and `runtime/solar/README.upstream.md` come from
  the upstream repository but have no file-specific license notice. They are
  conservatively recorded as LGPL-2.1-only based on the upstream repository's
  `LICENSE` file.
- The wrapper contains small portability changes to the copied runtime,
  including the `std::isnan` compatibility fix and makefile portability
  settings. Modified upstream files retain their upstream license category.

The upstream LGPL-2.1 text is preserved verbatim at
`runtime/solar/LICENSE`. Because LGPL version 3 supplements GPL version 3, the
distribution also includes the official texts at `licenses/GPL-3.0.txt` and
`licenses/LGPL-3.0.txt`.

The upstream root license and the file-specific source notices name different
LGPL versions. This distribution does not reinterpret or remove either notice;
it preserves both and reports their file-level scope conservatively.
