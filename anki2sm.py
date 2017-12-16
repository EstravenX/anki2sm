#!/usr/bin/python3
import re
import shutil
import click
import magic
import json
import sqlite3
from pyquery import PyQuery as pq
import itertools

from zipfile import ZipFile
from pathlib import Path

from yattag import Doc

TMP = "out/out_files/elements"

@click.command()
@click.option('--file', help='Filename.')
@click.option('--v', default=True, help='Filename.')
def hello(file, v):
  """Simple program that greets NAME for a total of COUNT times."""
  #for x in range(count):
  #  click.echo(click.style('Hello {}!'.format(name), fg='green'))

  p = unzip_file(Path(file))
  media = unpack_media(p)
  out = Path("out")
  out.mkdir(parents=True, exist_ok=True)
  elements = Path("{}/out_files/elements".format(out.as_posix()))
  elements.mkdir(parents=True, exist_ok=True)
  for k in media:
    shutil.move(p.joinpath(k).as_posix(), elements.joinpath(media[k]).as_posix())

  doc = unpack_db(p)

  with open("{}/out.xml".format(out.as_posix()), "w") as f:
    f.write(doc.getvalue())
  return 0

# @Todo: use temporary dir
def unzip_file(zipfile_path: Path) -> Path:
  if "zip" not in magic.from_file(zipfile_path.as_posix(), mime=True):
    print("apkg does not appear to be a ZIP file...")
    exit(1)
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
  sep = "\x1f" #some kind of control code that is not valid XML
  get_id = get_id_func()



  with tag('SuperMemoCollection'):
    with tag('Count'):
      text('3')
    with tag("SuperMemoElement"):
      with tag('ID'):
        text(get_id())
      with tag('Title'): #Items don't have titles
        text('Test')
      with tag('Type'): #Concept, Topic or Item
        text('Topic')
      for row in cursor.fetchall(): # @Todo, each collection should have its own concept or topic
        id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data = row
        qs = flds.split(sep)
        e = ""
        if isinstance(flds, str):
          e += flds
        if isinstance(flds, str):
          sfld += sfld
        d = pq(e)
        img = d("img").attr("src") or "" #@Todo: multiple images
        img_path = ""
        if img:
          img_path = "[SecondaryStorage]\\{}".format(img)
        #anki supports (claimed)
        #jpg png gif tiff svg tif jpeg mp3 ogg wav avi ogv
        #mpg mpeg mov mp4 mkv ogx ogv oga flv swf flac
        #sm17 supports (known)
        #jpg png gif bmp jpeg mp3 avi mp4
        content_sound = ()
        content_video = ()
        if "[sound:" in e: #@Todo: what happens if [ or ] is in the name?
          g = re.search("\[sound\:([^\]]+)", e)
          for p in g.groups():
            m = Path("{}/{}".format(TMP,p))
            if m.exists():
              if any([ext in m.suffix for ext in ["mp3", "ogg", "wav"]]) \
                  or "audio" in magic.from_file(m.as_posix(), mime=True):
                content_sound = content_sound + (p,)
              if any([ext in m.suffix for ext in ["mp4", "wmv", "mkv"]]) \
                  or "video" in magic.from_file(m.as_posix(), mime=True):
                content_video = content_video + (p,)
        with tag('SuperMemoElement'):
          with tag('ID'):
            text(get_id())
          with tag('Type'):
            text('Item')
          with tag('Content'): #zero or more of Question Answer Sound Video Image Binary
            with tag('Question'):
              text(strip_control_characters(qs[0]))
            with tag('Answer'):
              text(strip_control_characters(qs[1]))
            if img:
              with tag('Image'):
                with tag('URL'):
                  text(img_path)
                with tag('Name'):
                  text(img)
            for s in content_video:
              with tag('Video'):
                with tag('URL'):
                  text("[SecondaryStorage]\\{}".format(s))
                with tag('Name'):
                  text(s)
            for s in content_sound:
              with tag('Sound'):
                with tag('URL'):
                  text("[SecondaryStorage]\\{}".format(s))
                with tag('Name'):
                  text(s)
                with tag('Text'):
                  text("")
          with tag("LearningData"): #@Todo, convert anki learning data to sm
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
  pp("Amount of cards: {}".format(int(get_id())-1))
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
