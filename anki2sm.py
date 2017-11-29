import shutil
import click
import magic
import json
import sqlite3
import itertools

from zipfile import ZipFile
from pathlib import Path

from yattag import Doc

@click.command()
@click.option('--file', help='Filename.')
@click.option('--v', default=True, help='Filename.')
def hello(file, v):
  """Simple program that greets NAME for a total of COUNT times."""
  #for x in range(count):
  #  click.echo(click.style('Hello {}!'.format(name), fg='green'))

  p = unzip_file(Path(file))
  media = unpack_media(p)
  doc = unpack_db(p)
  out = Path("out")
  out.mkdir(parents=True, exist_ok=True)
  with open("out/out.xml", "w") as f:
    f.write(doc.getvalue())
  for k in media:
    shutil.move(p.joinpath(k).as_posix(), out.joinpath(media[k]).as_posix())
  return 0


def unzip_file(zipfile_path: Path) -> Path:
  assert "zip" in magic.from_file(zipfile_path.as_posix(), mime=True)
  with ZipFile(zipfile_path.as_posix(), 'r') as apkg:
    apkg.extractall(zipfile_path.stem)
  return Path(zipfile_path.stem)

def get_id_func():
  counter = itertools.count()
  next(counter)

  def p():
    return str(next(counter))
  return p

def unpack_db(path: Path):
  conn = sqlite3.connect(path.joinpath("collection.anki2").as_posix())
  cursor = conn.cursor()

  doc, tag, text = Doc().tagtext()

  cursor.execute("SELECT * FROM notes")
  sep = "\x1f"
  get_id = get_id_func()

  with tag('SuperMemoCollection'):
    with tag('Count'):
      text('3')
    with tag("SuperMemoElement"):
      with tag('ID'):
        text(get_id())
      with tag('Title'):
        text('Test')
      with tag('Type'):
        text('Topic')
      for row in cursor.fetchall():
        id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data = row
        qs = flds.split(sep)
        with tag('SuperMemoElement'):
          with tag('ID'):
            text(get_id())
          with tag('Title'):
            text(strip_control_characters(qs[0]))
          with tag('Type'):
            text('Item')
          with tag('Content'):
            with tag('Question'):
              text(strip_control_characters(qs[0]))
            with tag('Answer'):
              text(strip_control_characters(qs[1]))
            with tag('Image'):
              with tag('Url'):
                text("")
              with tag('Name'):
                text("")
          with tag("LearningData"):
            with tag("Interval"):
              text("1")
            with tag("Repetitions"):
              text("1")
            with tag("Lapses"):
              text("0")
            with tag("LastRepetition"):
              text("29.11.2017")
            with tag("AFactor"):
              text("")
            with tag("UFactor"):
              text("")
            with tag("RepHist"):
              text("")


  return doc

def unpack_media(media_dir: Path):
  if not media_dir.exists():
    raise FileNotFoundError

  with open(media_dir.joinpath("media").as_posix(), "r") as f:
    m = json.loads(f.read())
    pp("Amount of media files: {}".format(len(m)))
  return m



def strip_control_characters(input):
  if input:
    import re

    # unicode invalid characters
    RE_XML_ILLEGAL = u'([\u0000-\u0008\u000b-\u000c\u000e-\u001f\ufffe-\uffff])' + \
                     u'|' + \
                     u'([%s-%s][^%s-%s])|([^%s-%s][%s-%s])|([%s-%s]$)|(^[%s-%s])' % \
                     (chr(0xd800), chr(0xdbff), chr(0xdc00), chr(0xdfff),
                      chr(0xd800), chr(0xdbff), chr(0xdc00), chr(0xdfff),
                      chr(0xd800), chr(0xdbff), chr(0xdc00), chr(0xdfff),
                      )
    input = re.sub(RE_XML_ILLEGAL, "", input)

    # ascii control characters
    input = re.sub(r"[\x01-\x1F\x7F]", "", input)

  return input
  
def pp(p):
  click.secho(">> ", fg="green", nl=False)
  click.echo(p)


if __name__ == '__main__':
    hello()
