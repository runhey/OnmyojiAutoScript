# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from fastapi import APIRouter


home_app = APIRouter(
    prefix="/home",
    tags=["home"],
)

@home_app.get('/test')
async def home_test():
    return {'message':'test'}
#  gcc -Wall -pedantic -shared -fPIC -o group_work.so group_work.c -lwiringPi
@home_app.get('/home_menu')
async def home_menu():
    return {'Home': [], 'Updater': [], 'Tool': []}


