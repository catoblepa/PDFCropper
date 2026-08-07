i18n = import('i18n')

desktop_file = i18n.merge_file(
  input: 'io.github.catoblepa.Bounds.desktop.in',
  output: 'io.github.catoblepa.Bounds.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications'
)
