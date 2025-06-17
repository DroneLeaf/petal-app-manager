# petal-app-manager

ensure `python3-dev` is installed

```bash
sudo apt-get install python3-dev
```

or for specific python versions

```bash
sudo apt-get install python3.11-dev
```

We need to make sure the GCC compiler is used for building `pymavlink` from source

```bash
export CC=gcc

# Try installing again
pdm install -G dev
```