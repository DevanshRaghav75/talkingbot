# talkingbot

Create docker image

docker build -t talkingbot .

Run docker image with puppetron host as env variable and config file using volume

docker run -it --rm --name chat -e puppetron='http://127.0.0.1:8080/screenshot/' --net=host -v /docker/talkingbot/config:/config chatboto




--- puppetron

Run puppetron and list on port 8080

docker run  --rm --p 8080:3000--name puppetron moonlightwork/puppetron


