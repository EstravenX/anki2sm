import re
import shutil
import click
import magic
import json
import sqlite3
import os
import shutil 
from pyquery import PyQuery as pq
import itertools
from os import listdir
from os.path import isfile, join
from bs4 import BeautifulSoup as Soup
from zipfile import ZipFile
from pathlib import Path
import datetime
from yattag import Doc
import fnmatch

TMP = "out/out_files/elements"
urls = []
#@click.command()
#@click.option('--file', help='Filename.')
#@click.option('--v', default=True, help='Filename.')

def hello(file, v):
  """Insert helptext here."""
  p = unzip_file(Path(file))
  if p:
    media = unpack_media(p)
    out = Path("out")
    out.mkdir(parents=True, exist_ok=True)
    elements = Path(f"{out.as_posix()}/out_files/elements")
    elements.mkdir(parents=True, exist_ok=True)
    for k in media:
      try:
        shutil.move(p.joinpath(k).as_posix(), elements.joinpath(media[k]).as_posix())
      except:
        pass
    
    doc = unpack_db(p)

    with open(f"{out.as_posix()}/"+os.path.split(file)[-1].split(".")[0]+".xml", "w", encoding="utf-8") as f:
      f.write(doc.getvalue())
    return 0
  else:
    er("Cannot convert ",os.path.basename(file) )
    return -1

def unzip_file(zipfile_path: Path) -> Path:
  if "zip" not in magic.from_file(zipfile_path.as_posix(), mime=True):
    ep("apkg does not appear to be a ZIP file...")
    return -1
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
        text(str(os.path.split(str(Path))[-1].split(".")[0]))
      with tag('Type'): #Concept, Topic or Item
        text('Topic')
      for row in cursor.fetchall(): # @Todo, each collection should have its own concept or topic // donot understand this
        id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data = row
        qs = flds.split(sep)
        for z in range(len(qs)-1):
                if qs[z]!="":
                        qs[z]=qs[z]+'<br>'
        e = ""
        if isinstance(flds, str):
          e += flds
        if isinstance(flds, str):
          sfld += sfld
        d = pq(e)

        #anki supports:
        #jpg png gif tiff svg tif jpeg mp3 ogg wav avi ogv
        #mpg mpeg mov mp4 mkv ogx ogv oga flv swf flac
        
        #sm17 supports (known)
        #jpg png gif bmp jpeg mp3 avi mp4
        Content_Sound = ()
        Content_Video = ()
        Content_Images=()
        if 'img' in e:
          img_list = re.findall('<img.*?src="(.*?)"[^\>]+>', str(d))
          for imgs in img_list:
            Content_Images=Content_Images+(imgs,)

        if "[sound:" in e: #@Todo: what happens if [ or ] is in the name?//yea need to fix this
          g = re.search("\[sound\:([^\]]+)", e)
          for p in g.groups():
            m = Path("{}/{}".format(TMP,p))
            if m.exists():
              if any([ext in m.suffix for ext in ["mp3", "ogg", "wav"]]) \
                  or "audio" in magic.from_file(m.as_posix(), mime=True):
                Content_Sound = Content_Sound + (p,)
              if any([ext in m.suffix for ext in ["mp4", "wmv", "mkv"]]) \
                  or "video" in magic.from_file(m.as_posix(), mime=True):
                Content_Video = Content_Video + (p,)

        with tag('SuperMemoElement'):
          with tag('ID'):
            text(get_id())
          with tag('Type'):
            text('Item')
          with tag('Content'): #zero or more of Question Answer Sound Video Image Binary
            with tag('Question'):
              a = strip_control_characters(qs[0])
              a = a.encode("ascii", "xmlcharrefreplace").decode("utf-8")
              text(a)
              html = Soup(a,'html.parser')
              m=[p['href'] for p in html.find_all('a') ]
              urls.append(m[0]) if len(m) else ""
            
            with tag('Answer'):
              a = strip_control_characters(" ".join(qs[1:]))
              a = a.encode("ascii", "xmlcharrefreplace").decode("utf-8")
              text(a)

            for img in Content_Images:
              with tag('Image'):
                with tag('URL'):
                  text("C:\\ProgramData\\smmedia\\{}".format(img))
                with tag('Name'):
                  text(img)

            for s in Content_Video:
              with tag('Video'):
                with tag('URL'):
                  text("C:\\Users\\polit\\AppData\\Roaming\\smmedia\\{}".format(s))
                with tag('Name'):
                  text(s)

            for s in Content_Sound:
              with tag('Sound'):
                with tag('URL'):
                  text("C:\\ProgramData\\smmedia\\{}".format(s))
                with tag('Name'):
                  text(s)
                with tag('Text'):
                  text("")

          with tag("LearningData"): #@Todo, convert anki learning data to sm //anki's database is a mess 
            with tag("Interval"):
              text("1")
            with tag("Repetitions"):
              text("1")
            with tag("Lapses"):
              text("0")
            with tag("LastRepetition"):
              text(datetime.date.today().strftime("%d.%m.%Y"))
            with tag("AFactor"):
              text("3.92") # values taken off untrained data in SM
            with tag("UFactor"):
              text("3")
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
    #removing sound tags
    input = re.sub(r"\[sound\:([^\]]+)]","",input)

  return input

def ep(p):
  click.secho(str(">> "+p), fg="red", nl=False)

def pp(p):
  click.secho(">> ", fg="green", nl=False)
  click.echo(p)


if __name__ == '__main__':
    IR_yee_or_nay = str(input("Do you want to scrape annotations into a bat file for IR (Y/N): "))
    mypath =str(os.getcwd()+"\\apkgs\\")
    apkgfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
    for i in range(len(apkgfiles)):
      hello(mypath+apkgfiles[i],v=True)
      print("Done with ",i+1,"out of",len(apkgfiles))
      
      try:
        shutil.rmtree(os.path.splitext(apkgfiles[i])[0])
      except OSError as e:
        print ("Error: %s - %s." % (e.filename, e.strerror))

    #creating smmedia if it doesnot exist
    if not os.path.exists('C:\\ProgramData\\smmedia'):
      try:
        os.makedirs('C:\\ProgramData\\smmedia')
      except OSError as e:
        if e.errno != errno.EEXIST:
          raise
    #moving media files to smmedia
    files = os.listdir(os.getcwd()+"\\out\\out_files\\elements")
    for f in files:
        shutil.move(os.getcwd()+"\\out\\out_files\\elements\\"+f, 'C:\\ProgramData\\smmedia')
    #deleting temp media files
    try:
      shutil.rmtree(os.getcwd()+"\\out\\out_files\\elements")
      shutil.rmtree(os.getcwd()+"\\out\\out_files")
    except OSError as e:
      print ("Error: %s - %s." % (e.filename, e.strerror))


    if IR_yee_or_nay in ['1','Y','y','ye','yes'] and urls:
      with open('IR.bat', 'w')as ir:
        ir.writelines(['@echo off\n\n']+[str("start /d  IEXPLORE.EXE"+i+'\n') for i in urls])
    meh=input("Press Enter to Exit")