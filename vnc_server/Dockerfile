FROM python

WORKDIR /src

COPY ./requirements.txt /src/
RUN pip install -r requirements.txt
COPY . .
 #ENV VIRTUAL_ENV=~/vnc_server/venv/bin/activate

#RUN python3 -m venv $VIRTUAL_ENV

#ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /src/network



# DB Must be running first.
# Change this to use gunicorn in prod rather than running py (Running like this using flask dev server is insecure)
CMD ["python", "./flaskAPI.py"]

EXPOSE 5000
