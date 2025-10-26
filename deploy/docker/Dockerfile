# docker build -t qwerty/oas:latest .
# docker run -v ${PWD}:/app/OnmyojiAutoScript -p 22288:22288 --name oas -it --rm qwerty/oas


FROM python:3.10-slim-bookworm

WORKDIR /app/OnmyojiAutoScript

COPY requirements.txt /tmp/requirements.txt

# python:3.10-slim is based on debian:12, apt source from https://developer.aliyun.com/mirror/debian
RUN echo "\
deb https://mirrors.cloud.tencent.com/debian/ bookworm main non-free non-free-firmware contrib \n\
deb-src https://mirrors.cloud.tencent.com/debian/ bookworm main non-free non-free-firmware contrib \n\
deb https://mirrors.cloud.tencent.com/debian-security/ bookworm-security main \n\
deb-src https://mirrors.cloud.tencent.com/debian-security/ bookworm-security main \n\
deb https://mirrors.cloud.tencent.com/debian/ bookworm-updates main non-free non-free-firmware contrib \n\
deb-src https://mirrors.cloud.tencent.com/debian/ bookworm-updates main non-free non-free-firmware contrib \n\
deb https://mirrors.cloud.tencent.com/debian/ bookworm-backports main non-free non-free-firmware contrib \n\
deb-src https://mirrors.cloud.tencent.com/debian/ bookworm-backports main non-free non-free-firmware contrib \
    "\
> /etc/apt/sources.list\
 && apt update \
 && apt install -y git adb libgomp1 openssh-client \
 && git config --global --add safe.directory '*' \
 && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
 && echo 'Asia/Shanghai' > /etc/timezone \
 && pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
 && pip install -r /tmp/requirements.txt \
 && pip uninstall -y opencv-python\
 && pip uninstall -y opencv-python-headless\
 && pip install opencv-python-headless==4.7.0.72\
 && rm /tmp/requirements.txt \
 && rm -r ~/.cache/pip

CMD python server.py
#CMD /bin/bash