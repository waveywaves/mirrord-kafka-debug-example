# mirrord-kafka-debug-example

```
docker compose up --build
```

```
conda create -n kafka-debug python=3.9 -y && conda activate kafka-debug && pip install -r requirements.txt
conda activate kafka-debug
```

```
APP_MODE=consumer mirrord exec -f .mirrord/mirrord.json -- python app.py
```