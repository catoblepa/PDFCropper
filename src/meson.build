pkgdatadir = get_option('prefix') / get_option('datadir') / 'pdfcropper'

sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'canvas.py',
  'dialogs.py',
  'panels.py',
  'ocr.py',
  'style.css',
]

install_data(sources, install_dir: pkgdatadir)

conf = configuration_data()
conf.set('PYTHON', find_program('python3').full_path())
conf.set('pkgdatadir', pkgdatadir)
conf.set('APP_VERSION', meson.project_version())

version_conf = configure_file(
  input: 'version.py.in',
  output: 'version.py',
  configuration: conf,
)
install_data(version_conf, install_dir: pkgdatadir)

configure_file(
  input: 'pdfcropper.in',
  output: 'pdfcropper',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)
