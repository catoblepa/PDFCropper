i18n = import('i18n')

desktop_file = i18n.merge_file(
  input: 'io.github.catoblepa.Bounds.desktop.in',
  output: 'io.github.catoblepa.Bounds.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications'
)

appstream_file = i18n.merge_file(
  input: 'io.github.catoblepa.Bounds.metainfo.xml',
  output: 'io.github.catoblepa.Bounds.metainfo.xml',
  type: 'xml',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

install_data(
  'icons/scalable/apps/io.github.catoblepa.Bounds.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps'
)
