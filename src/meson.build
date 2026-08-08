pkgdatadir = get_option('prefix') / get_option('datadir') / 'bounds'

sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'canvas.py',
  'dialogs.py',
  'style.css',
]

install_data(sources, install_dir: pkgdatadir)

conf = configuration_data()
conf.set('PYTHON', find_program('python3').full_path())
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'bounds.in',
  output: 'bounds',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)
