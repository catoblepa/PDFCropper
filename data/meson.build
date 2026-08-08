i18n = import('i18n')

desktop_file = i18n.merge_file(
  input: 'io.github.catoblepa.PDFCropper.desktop.in',
  output: 'io.github.catoblepa.PDFCropper.desktop',
  type: 'desktop',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'applications'
)

appstream_file = i18n.merge_file(
  input: 'io.github.catoblepa.PDFCropper.metainfo.xml',
  output: 'io.github.catoblepa.PDFCropper.metainfo.xml',
  type: 'xml',
  po_dir: '../po',
  install: true,
  install_dir: get_option('datadir') / 'metainfo'
)

install_data(
  'icons/scalable/apps/io.github.catoblepa.PDFCropper.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/scalable/apps'
)

install_data(
  'icons/symbolic/actions/crop-symbolic.svg',
  install_dir: get_option('datadir') / 'icons/hicolor/symbolic/actions'
)

install_data(
  'io.github.catoblepa.PDFCropper.gschema.xml',
  install_dir: get_option('datadir') / 'glib-2.0/schemas'
)

gnome = import('gnome')
gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
)

install_data(
  'icons/index.theme',
  install_dir: get_option('datadir') / 'icons/hicolor'
)
