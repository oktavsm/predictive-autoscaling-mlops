FROM texlive/texlive:latest-medium

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies, required fonts, build tools, and biber
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-crosextra-carlito \
    fonts-liberation \
    latexmk \
    biber \
    make \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install additional TeX Live packages required for the skripsi template
RUN (tlmgr update --self || true) && \
    (tlmgr install \
    titlesec \
    biblatex \
    logreq \
    enumitem \
    fancyhdr \
    indentfirst \
    || true)
