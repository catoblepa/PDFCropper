i18n = import('i18n')

desktop_file = i18n.merge_file(
  input: 'io.github.catoblepa.PDFBounds.desktop.in',
  output: 'io.github.catoblepa.PDFBounds.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications'
)

appstream_file = i18n.merge_file(
  input: 'io.github.catoblepa.PDFBounds.metainfo.xml',
  output: 'io.github.catoblepa.PDFBounds.metainfo.xml',
  type: 'xml',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

install_data(
  'icons/scalable/apps/io.github.catoblepa.PDFBounds.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps'
)
