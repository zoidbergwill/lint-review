FROM ubuntu:16.04
ENV REFRESHED_AT 2016-05-21

RUN apt-get update && \
    apt-get install -y curl && \
    curl -sL https://deb.nodesource.com/setup_6.x | bash - && \
    curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - && \
    echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list && \
    apt-get update && \
    apt-get install -y \
    python2.7 python-pip \
    php \
    php-pear \
    git \
    ruby \
    ruby-dev \
    shellcheck \
    luarocks \
    libxml2 \
    libffi-dev \
    yarn \
    zlib1g-dev \
    build-essential && \
    apt-get -y autoremove && \
    apt-get -y clean  && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code
RUN pear install PHP_CodeSniffer
RUN luarocks install luacheck
RUN gem install bundler

ADD package.json /code/
RUN yarn

ENV BUNDLE_SILENCE_ROOT_WARNING 1
ADD Gemfile Gemfile.lock /code/
RUN bundler install --system

ADD requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt
ADD . /code
RUN pip install .
RUN cp /code/settings.sample.py /code/settings.py
