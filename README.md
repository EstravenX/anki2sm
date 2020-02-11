# Anki to SuperMemo 17 converter
  anki2sm is a python script that is meant to batch convert anki decks into supermemo decks, including audios, images and videos. The scripts comes with an additional feature of extracting annotated links, for incremental reading. It creates a bat file that when run opens exploerer with multiple tabs. You can open supermemo to import these webpages.This script is meant to run on Windows.  

### Steps for usage:
- clone this repo
- make sure requirements.txt is met 
- delete sample apkg in apkgs folder and paste your own in there
- run script and profit! (python anki2sm.py )

##### Some Notes:
  Media from anki is stored into ```C:\ProgramData\smmedia```. You donot need to create the directory the script creates it. Tested with images and audio. Some cool stuff could be added, check code if you are willing to work on them.

# TODO: 
  1) [ ] Bug test it.
  2) [ ] Anki progress import.
  3) [ ] Each collection should have its own concept or topic.
  4) [ ] if ```or``` is in a media's filename

# Special Thanks to:
-https://github.com/KeepOnSurviving

-https://github.com/cutie
