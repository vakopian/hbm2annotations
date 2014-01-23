from BeautifulSoup import BeautifulSoup
import re, sys


def processHbm(hbm):
    with open(hbm) as hbmFile:
        soup = BeautifulSoup(hbmFile)
        for cls in soup.findAll('class'):
            clsName = cls['name']
            table = cls['table']


if __name__ == '__main__':
    processHbm(sys.argv[1])

