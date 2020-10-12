import errno
import os
import re
import shutil
import sqlite3
from datetime import datetime
from os import listdir
from os.path import isfile, join
from pathlib import Path
import json
from collections import defaultdict
from zipfile import ZipFile

from magic import magic
import Formatters
import mustache
from yattag import Doc
import itertools
import premailer
import cssutils
import logging
import click
from Utils.HtmlUtils import \
	(
	wrapHtmlIn,
	strip_control_characters,
	cleanHtml,
	get_rule_for_selector,
	insertHtmlAt
)
from Models import \
	(
	Model,
	Template,
	Card,
	Collection,
	Note,
	EmptyString
)

cssutils.log.setLevel(logging.CRITICAL)

SUB_DECK_MARKER = '<sub_decks>'

Anki_Collections = defaultdict(dict, ((SUB_DECK_MARKER, []),))
AnkiNotes = {}
AnkiModels = {}
totalCardCount = 0

doc, tag, text = Doc().tagtext()

IMPORT_LEARNING_DATA = False
IMAGES_AS_COMPONENT = False
IMAGES_TEMP = ()
FAILED_DECKS = []


# ============================================ Other Util Stuff But Deck related =================================

def getDeckFromID(d, did: str):
	res = None
	for key, value in d.items():
		if key == SUB_DECK_MARKER:
			if value:
				for col in value:
					if col.did == did and res is None:
						res = col
		else:
			if isinstance(value, dict):
				if res is None:
					res = getDeckFromID(value, did)
			else:
				if isinstance(value, Collection):
					if value.did == did and res is None:
						res = value
	return res


def getTemplateofOrd(templates, ord: int):
	for templ in templates:
		if (templ.ord == ord):
			return templ


def get_id_func():
	counter = itertools.count()
	next(counter)
	
	def p():
		return str(next(counter))
	
	return p


get_id = get_id_func()


#   Commented until a better understanding of anki is reached
#   	Code Source: https://groups.google.com/d/msg/supermemo_users/dTzhEog6zPk/8wqBk4qcCgAJ
#       Its Author: Mnd Mau
# def convert_time(x):
# 	if x == '':
# 		return ('')
# 	space = x.find(' ')
# 	if space == -1 and 'm' in x:
# 		return (1)
# 	if '(new)' in x:
# 		return (0)
# 	number = float(x[:space])
# 	if 'months' in x:
# 		return (round(number * 30))
# 	elif 'years' in x:
# 		return (round(number * 365))
# 	elif 'day' in x:
# 		return (round(number))
#
#
# def scale_afactor(a, min_ease, max_ease):
# 	return (6.868 - 1.3) * ((a - min_ease) / (max_ease - min_ease)) + 1.3

# ============================================= Some Util Functions =============================================

# Error Print
def ep(p) -> None:
	"""error print"""
	click.secho(str(">> " + p), fg="red", nl=False)


def pp(p) -> None:
	"""pretty print"""
	click.secho(">> ", fg="green", nl=False)
	click.echo(p)


def wp(p) -> None:
	"""warning print - yellow in color"""
	click.secho(p, fg="yellow", nl=True)


def resetGlobals() -> None:
	global Anki_Collections, AnkiNotes, AnkiModels, totalCardCount, doc, tag, text, IMAGES_TEMP
	Anki_Collections = defaultdict(dict, ((SUB_DECK_MARKER, []),))
	AnkiNotes = {}
	AnkiModels = {}
	IMAGES_TEMP = ()
	totalCardCount = 0
	doc, tag, text = Doc().tagtext()


def unpack_db(path: Path) -> None:
	conn = sqlite3.connect(path.joinpath("collection.anki2").as_posix())
	cursor = conn.cursor()
	
	cursor.execute("SELECT * FROM col")
	for row in cursor.fetchall():
		did, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags = row
		buildColTree(decks)
		print("Building Collection Tree Completed..")
		buildModels(models)
		print("Building Models Completed...")
		print(getDeckFromID(Anki_Collections,"1600222419614"))
		buildNotes(path)
		print("Building Cards Completed...")
		buildCardsAndDeck(path)
		print("Card and Deck Completed...")
	# prettyDeckTree(Anki_Collections)
	export(path)


def unpack_media(media_dir: Path):
	# if not media_dir.exists():
	#	raise FileNotFoundError
	
	with open(media_dir.joinpath("media").as_posix(), "r") as f:
		m = json.loads(f.read())
		pp("Amount of media files: {}".format(len(m)))
	return m


def unzip_file(zipfile_path: Path) -> Path:
	if "zip" not in magic.from_file(zipfile_path.as_posix(), mime=True):
		ep("apkg does not appear to be a ZIP file...")
		return -1
	with ZipFile(zipfile_path.as_posix(), 'r') as apkg:
		apkg.extractall(zipfile_path.stem)
	return Path(zipfile_path.stem)


# ============================================= Deck Builder Functions =============================================

def attach(key, branch, trunk) -> None:
	"""Insert a branch of Decks on its trunk."""
	parts = branch.split('::', 1)
	if len(parts) == 1:  # branch is a leaf sub-deck
		trunk[SUB_DECK_MARKER].append(Collection(key, parts[0]))
	else:
		node, others = parts
		if node not in trunk:
			trunk[node] = defaultdict(dict, ((SUB_DECK_MARKER, []),))
		attach(key, others, trunk[node])


def prettyDeckTree(d, indent=0):
	for key, value in d.items():
		if key == SUB_DECK_MARKER:
			if value:
				print('  ' * indent + str(value))
		else:
			print('  ' * indent + str(key))
			if isinstance(value, dict):
				prettyDeckTree(value, indent + 1)
			else:
				print('  ' * (indent + 1) + str(value))


def isSubDeck(d: dict, name: str) -> bool:
	res = False
	for key, value in d.items():
		if key == name:
			res = True
		else:
			if isinstance(value, dict):
				if not res:
					res = isSubDeck(value, name)
	return res


def getSubDeck(d: dict, name: str) -> Collection:
	res = None
	for key, value in d.items():
		if key == SUB_DECK_MARKER:
			if value:
				for col in value:
					if col.name == name:
						res = col
		else:
			if isinstance(value, dict):
				if res is None :
					res = getSubDeck(value, name)
	print(res)
	return res

def buildColTree(m: str):
	global Anki_Collections
	y = json.loads(m)
	decks = []
	for k in y.keys():
		attach(k, y[k]["name"], Anki_Collections)


def buildModels(t: str):
	global AnkiModels
	y = json.loads(t)
	templates = []
	flds = []
	for k in y.keys():
		AnkiModels[str(y[k]["id"])] = Model(str(y[k]["id"]), y[k]["type"], y[k]["css"])
		
		for fld in y[k]["flds"]:
			flds.append((fld["name"], fld["ord"]))
		flds.sort(key=lambda x: int(x[1]))
		
		AnkiModels[str(y[k]["id"])].flds = tuple([f[0] for f in flds])
		
		for tmpl in y[k]["tmpls"]:
			templates.append(Template(tmpl["name"], tmpl["qfmt"], tmpl["did"], tmpl["bafmt"], tmpl["afmt"], tmpl["ord"],
			                          tmpl["bqfmt"]))
		
		AnkiModels[str(y[k]["id"])].tmpls = tuple(templates)
		templates = []
		flds = []


def buildStubbleDict(note: Note):
	cflds = note.flds.split(u"")
	temp_dict = {}
	for f, v in zip(note.model.flds, cflds):
		temp_dict[str(f)] = str(v)
	temp_dict["Tags"] = [i for i in note.tags if i]
	return temp_dict


def buildNotes(path: Path):
	global AnkiNotes
	conn = sqlite3.connect(path.joinpath("collection.anki2").as_posix())
	cursor = conn.cursor()
	cursor.execute("SELECT * FROM notes")
	for row in cursor.fetchall():
		nid, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data = row
		reqModel = AnkiModels[str(mid)]
		AnkiNotes[str(nid)] = Note(reqModel, flds)
		AnkiNotes[str(nid)].tags = EmptyString(tags).split(" ")


#   Commented until a better understanding of anki is reached
#   	Source: https://groups.google.com/d/msg/supermemo_users/dTzhEog6zPk/8wqBk4qcCgAJ
#       Author: Mnd Mau
#
# def buildCardData(card: Card, minEase, maxEase):
# 	if element[5] == '':
# 		last_repetition = datetime.strptime(element[7], '%Y-%m-%d')
# 	else:
# 		last_repetition = datetime.strptime(element[5], '%Y-%m-%d')
# 	current_interval = convert_time(element[2])
# 	prior_interval = convert_time(element[6])
# 	if prior_interval == '':
# 		card.ufactor = format(current_interval, '.3f')
# 	else:
# 		card.ufactor = format(current_interval / prior_interval, '.3f')
# 	if '(new)' in element[8]:
# 		card.afactor = '3.000'
# 	else:
# 		ease = float(element[8][:-1])
# 		card.afactor = str(format(scale_afactor(ease, minEase, maxEase), '.3f'))
#

def buildCardsAndDeck(path: Path):
	global AnkiNotes, AnkiModels, Anki_Collections, totalCardCount, FAILED_DECKS
	conn = sqlite3.connect(path.joinpath("collection.anki2").as_posix())
	cursor = conn.cursor()
	cursor.execute(
		"SELECT * FROM cards ORDER BY factor ASC")  # min ease would at rows[0] and max index would be at rows[-1]
	rows = cursor.fetchall()
	
	for row in rows:
		cid, nid, did, ordi, mod, usn, crtype, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data = row
		reqNote = AnkiNotes[str(nid)]
		genCard = None
		
		if reqNote.model.type == 0:
			reqTemplate = getTemplateofOrd(reqNote.model.tmpls, int(ordi))
			
			questionTg = "<style> " + buildCssForOrd(reqNote.model.css, ordi) \
			             + "</style><section class='card' style=\" height:100%; width:100%; margin:0; \">" \
			             + mustache.render(reqTemplate.qfmt, buildStubbleDict(reqNote)) + "</section>"
			answerTag = "<style> " + buildCssForOrd(reqNote.model.css, ordi) \
			            + "</style><section class='card' style=\" height:100%; width:100%; margin:0; \">" \
			            + mustache.render(reqTemplate.afmt, buildStubbleDict(reqNote)) + "</section>"
			questionTg = premailer.transform(questionTg)
			answerTag = premailer.transform(answerTag)
			genCard = Card(cid, questionTg, answerTag)
			
		elif reqNote.model.type == 1:
			reqTemplate = getTemplateofOrd(reqNote.model.tmpls, 0)
			
			mustache.filters["cloze"] = lambda txt: Formatters.cloze_q_filter(txt, str(int(ordi) + 1))
			
			css = reqNote.model.css
			css = buildCssForOrd(css, ordi) if css else ""
			
			questionTg = "<style> " + css + " </style><section class='card' style=\" height:100%; width:100%; margin:0; \">" \
			             + mustache.render(reqTemplate.qfmt, buildStubbleDict(reqNote)) + "</section>"
			
			mustache.filters["cloze"] = lambda txt: Formatters.cloze_a_filter(txt, str(int(ordi) + 1))
			
			answerTag = "<section class='card' style=\" height:100%; width:100%; margin:0; \">" \
			            + mustache.render(reqTemplate.afmt, buildStubbleDict(reqNote)) + "</section>"
			
			questionTg = premailer.transform(questionTg)
			answerTag = premailer.transform(answerTag)
			genCard = Card(cid, questionTg, answerTag)
			
		if genCard is not None:
			reqDeck = getDeckFromID(Anki_Collections, str(did))
			if reqDeck is not None:
				reqDeck.cards.append(genCard)
			else:
				if did not in FAILED_DECKS:
					FAILED_DECKS.append(did)
		else:
			if did not in FAILED_DECKS:
				FAILED_DECKS.append(did)
		totalCardCount += 1


def buildCssForOrd(css, ordi):
	pagecss = cssutils.parseString(css)
	defaultCardCss = get_rule_for_selector(pagecss, ".card")
	ordinalCss = get_rule_for_selector(pagecss, ".card{}".format(ordi + 1))
	try:
		ordProp = [prop for prop in ordinalCss.style.getProperties()]
		for dprop in defaultCardCss.style.getProperties():
			if (dprop.name in [n.name for n in ordProp]):
				defaultCardCss.style[dprop.name] = ordinalCss.style.getProperty(dprop.name).value
	except:
		pass
	return defaultCardCss.cssText


# ============================================= Import and Export Function =============================================

def export(file):
	global Anki_Collections
	out = Path("out")
	out.mkdir(parents=True, exist_ok=True)
	
	with tag('SuperMemoCollection'):
		with tag('Count'):
			text(str(totalCardCount))
		SuperMemoCollection(Anki_Collections)
	
	with open(f"{out.as_posix()}/" + os.path.split(file)[-1].split(".")[0] + ".xml", "w", encoding="utf-8") as f:
		f.write(doc.getvalue())


def start_import(file: str) -> int:
	p = unzip_file(Path(file))
	if p:
		media = unpack_media(p)
		out = Path("out")
		out.mkdir(parents=True, exist_ok=True)
		elements = Path(f"{out.as_posix()}/out_files/elements")
		try:
			os.makedirs(elements.as_posix())
		except:
			pass
		for k in media:
			try:
				shutil.move(p.joinpath(k).as_posix(), elements.joinpath(media[k]).as_posix())
			except:
				pass
		unpack_db(p)
		return 0
	else:
		ep("Cannot convert %s" % os.path.basename(file))
		return -1


# =============================================SuperMemo Xml Output Functions =============================================

def SuperMemoCollection(d: dict, indent=0):
	global doc, tag, text
	for key, value in d.items():
		if key == SUB_DECK_MARKER:
			if value:
				for col in value:
					if not isSubDeck(Anki_Collections, col.name):
						SuperMemoTopic(col, col.name)
		else:
			if isinstance(value, dict):
				with tag("SuperMemoElement"):
					with tag('ID'):
						text(get_id())
					with tag('Title'):
						text(str(key))
					with tag('Type'):
						text('Topic')
					SuperMemoCollection(value, indent=indent + 1)
					subdk = getSubDeck(Anki_Collections, key)
					if subdk:
						if subdk.cards is not None:
							for c in subdk.cards:
								SuperMemoElement(c)


def cardHasData(card: Card) -> bool:
	if card != None:
		return card.ufactor and card.afactor and \
		       card.interval and card.lapses and \
		       card.last_rep and card.repetitions
	else:
		return False


def SuperMemoElement(card: Card) -> None:
	global doc, tag, text, get_id, IMAGES_TEMP
	IMAGES_TEMP = ()
	
	QContent_Sounds = ()
	QContent_Videos = ()
	
	AContent_Sounds = ()
	AContent_Videos = ()
	
	if "[sound:" in str(card.q):
		g = re.search(r"(?:\[sound:)([^])(?:]+)(?:\])", str(card.q))
		if g is not None:
			for p in g.groups():
				m = Path("{}/{}".format("out/out_files/elements", p))
				if m.exists():
					if any([ext in m.suffix for ext in ["mp3", "ogg", "wav"]]) \
							or "audio" in magic.from_file(m.as_posix(), mime=True):
						QContent_Sounds = QContent_Sounds + (p,)
					if any([ext in m.suffix for ext in ["mp4", "wmv", "mkv"]]) \
							or "video" in magic.from_file(m.as_posix(), mime=True):
						QContent_Videos = QContent_Videos + (p,)
	
	if "[sound:" in str(card.a):
		g = re.search(r"(?:\[sound:)([^])(?:]+)(?:\])", str(card.a))
		if g is not None:
			for p in g.groups():
				m = Path("{}/{}".format("out/out_files/elements", p))
				if m.exists():
					if any([ext in m.suffix for ext in ["mp3", "ogg", "wav"]]) \
							or "audio" in magic.from_file(m.as_posix(), mime=True):
						AContent_Sounds = AContent_Sounds + (p,)
					if any([ext in m.suffix for ext in ["mp4", "wmv", "mkv"]]) \
							or "video" in magic.from_file(m.as_posix(), mime=True):
						AContent_Videos = AContent_Videos + (p,)
		
	card.q = Formatters.reSound.sub("", card.q)
	card.a = Formatters.reSound.sub("", card.a)
	
	enforceSectionJS = """<script>document.createElement("section");</script>"""
	liftIERestriction = """<meta http-equiv="X-UA-Compatible" content="IE=10">"""
	forcedCss = """<style>img{max-width:50%;}</style>"""
	with tag('SuperMemoElement'):
		with tag('ID'):
			text(get_id())
		with tag('Type'):
			text('Item')
		with tag('Content'):
			with tag('Question'):
				a = wrapHtmlIn(card.q, 'head', 'body')
				res = cleanHtml(a, imgcmp=IMAGES_AS_COMPONENT)
				if IMAGES_AS_COMPONENT:
					IMAGES_TEMP = IMAGES_TEMP + res["imgs"]
				a = insertHtmlAt(res["soup"], enforceSectionJS, 'head', 0)
				a = insertHtmlAt(a, liftIERestriction, 'head', 0)
				a = insertHtmlAt(a,forcedCss,'head',0)
				a = strip_control_characters(a)
				a = a.encode("ascii", "xmlcharrefreplace").decode("utf-8")
				text(a)
			
			for s in QContent_Videos:
				with tag('Video'):
					with tag('URL'):
						text(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\{}".format(s))
					with tag('Name'):
						text(s)
					with tag("Question"):
						text("T")
					with tag("Answer"):
						text("F")
			
			for s in QContent_Sounds:
				with tag('Sound'):
					with tag('URL'):
						text(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\{}".format(s))
					with tag('Name'):
						text(s)
					with tag('Text'):
						text("")
					with tag("Question"):
						text("T")
					with tag("Answer"):
						text("F")
			
			# html = Soup(a,'html.parser')
			# m=[p['href'] for p in html.find_all('a') ]
			# urls.append(m[0]) if len(m) else ""
			
			with tag('Answer'):
				res = cleanHtml(card.a, imgcmp=IMAGES_AS_COMPONENT)
				if IMAGES_AS_COMPONENT:
					IMAGES_TEMP = IMAGES_TEMP + res["imgs"]
				a = insertHtmlAt(res["soup"], enforceSectionJS, 'head', 0)
				a = insertHtmlAt(a, liftIERestriction, 'head', 0)
				a = insertHtmlAt(a, forcedCss, 'head', 0)
				a = strip_control_characters(a)
				a = a.encode("ascii", "xmlcharrefreplace").decode("utf-8")
				text(a)
			
			for s in AContent_Videos:
				with tag('Video'):
					with tag('URL'):
						text(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\{}".format(s))
					with tag('Name'):
						text(s)
					with tag("Question"):
						text("F")
					with tag("Answer"):
						text("T")
			
			for s in AContent_Sounds:
				with tag('Sound'):
					with tag('URL'):
						text(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\{}".format(s))
					with tag('Name'):
						text(s)
					with tag('Text'):
						text("")
					with tag("Question"):
						text("F")
					with tag("Answer"):
						text("T")
			
			for img in IMAGES_TEMP:
				with tag('Image'):
					with tag('URL'):
						text(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\{}".format(img))
					with tag('Name'):
						text(img)
			
			if False and cardHasData(card):
				with tag("LearningData"):
					with tag("Interval"):
						text("1")
					with tag("Repetitions"):
						text("1")
					with tag("Lapses"):
						text("0")
					with tag("LastRepetition"):
						text(datetime.date("").strftime("%d.%m.%Y"))
					with tag("AFactor"):
						text("3.92")
					with tag("UFactor"):
						text("3")


def SuperMemoTopic(col, ttl) -> None:
	global doc, tag, text, get_id
	with tag("SuperMemoElement"):
		with tag('ID'):
			text(get_id())
		with tag('Title'):
			text(str(ttl))
		# print(str(ttl))
		with tag('Type'):
			text('Topic')
		if col.cards != None:
			for c in col.cards:
				SuperMemoElement(c)


# ============================================= Main Function =============================================

def main():
	global AnkiNotes, totalCardCount, IMAGES_AS_COMPONENT
	
	mypath = str(os.getcwd() + "\\apkgs\\")
	apkgfiles = [f for f in listdir(mypath) if isfile(join(mypath, f))]
	
	if len(apkgfiles) == 0:
		ep("No apkg in apkgs folder.")
		exit(0)
	
	print("Do You want images as:")
	print("\tY - A separate component ")
	print("\tN - Embedded within the Html - experimental")
	tempInp = str(input(""))
	if tempInp.casefold() in "Y".casefold():
		IMAGES_AS_COMPONENT = True
	elif tempInp.casefold() != "N".casefold():
		print("Wrong input provided, proceeding as embedded")
	for i in range(len(apkgfiles)):
		start_import(mypath + apkgfiles[i])
		print("Done with ", i + 1, "out of", len(apkgfiles))
		resetGlobals()
		try:
			shutil.rmtree(os.path.splitext(apkgfiles[i])[0])
		except OSError as e:
			print("Error: %s - %s." % (e.filename, e.strerror))
	
	# creating smmedia if it doesnot exist
	if not os.path.exists(str(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\")):
		try:
			os.makedirs(str(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\"))
		except OSError as e:
			if e.errno != errno.EEXIST:
				raise
	
	# moving media files to smmedia
	files = os.listdir(os.getcwd() + "\\out\\out_files\\elements")
	for f in files:
		if f not in os.listdir(str(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\")):
			try:
				shutil.move(os.getcwd() + "\\out\\out_files\\elements\\" + f,
				            str(os.path.expandvars(r'%LocalAppData%') + "\\temp\\smmedia\\"))
			except:
				pass
	
	# deleting temp media files
	try:
		shutil.rmtree(os.getcwd() + "\\out\\out_files\\elements")
		shutil.rmtree(os.getcwd() + "\\out\\out_files")
	except OSError as e:
		print("Error: %s - %s." % (e.filename, e.strerror))
	print(totalCardCount)


if __name__ == '__main__':
	main()
	if len(FAILED_DECKS) > 0:
		wp("An Error occured while processing the following decks:")
		for i in FAILED_DECKS:
			print(i)
		wp(
			"Please send an email to anki2sm.dev@protonmail.com with the attached deck(s) and the failed deck ids above.")
