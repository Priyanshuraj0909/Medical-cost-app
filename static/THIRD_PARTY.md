# Locally served assets

- Chart.js 4.5.1, MIT license: `vendor/CHART-LICENSE.md`. Source: https://github.com/chartjs/Chart.js . Distributed UMD bundle copied from the pinned npm package.
- Noto Sans Devanagari via @fontsource/noto-sans-devanagari 5.2.8, SIL Open Font License: `fonts/OFL.txt`. Source: https://github.com/notofonts/devanagari . The two files are the original Devanagari subsets at weights 400 and 700, copied without modification.
- PWA icons are raster renderings of this repository's existing `favicon.svg`.

To refresh library assets intentionally, update the pinned npm dependency and copy its UMD bundle/license or font files to these locations, then run browser checks and update the service-worker cache contract if needed. Development node_modules are not deployed.
