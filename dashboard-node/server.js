const express = require('express');
const http = require('http');
const { WebSocketServer } = require('ws');
const path = require('path');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// 当前 Pipeline 状态
let pipelineState = {
  project: '', chapter: 0, mode: '',
  stages: [],
  status: 'idle',
  startTime: null,
};

// WebSocket 连接
wss.on('connection', (ws) => {
  ws.send(JSON.stringify({ type: 'full_state', data: pipelineState }));
});

function broadcast(msg) {
  wss.clients.forEach(c => { if (c.readyState === 1) c.send(JSON.stringify(msg)); });
}

// 接收 Python Pipeline 事件
app.post('/api/pipeline/start', (req, res) => {
  const { project, chapter, mode, stages } = req.body;
  pipelineState = {
    project, chapter, mode, stages: stages.map(s => ({ id: s, status: 'pending', time: null })),
    status: 'running', startTime: Date.now(),
  };
  broadcast({ type: 'full_state', data: pipelineState });
  res.json({ ok: true });
});

app.post('/api/pipeline/stage', (req, res) => {
  const { stage, status, time } = req.body;
  const s = pipelineState.stages.find(s => s.id === stage);
  if (s) { s.status = status; s.time = time; }
  broadcast({ type: 'stage_update', data: { stage, status, time } });
  if (status === 'error') broadcast({ type: 'alert', data: `${stage} 失败` });
  res.json({ ok: true });
});

app.post('/api/pipeline/complete', (req, res) => {
  const { words, elapsed } = req.body;
  pipelineState.status = 'done';
  pipelineState.words = words;
  pipelineState.elapsed = elapsed;
  broadcast({ type: 'complete', data: { words, elapsed } });
  res.json({ ok: true });
});

app.get('/api/state', (req, res) => res.json(pipelineState));

const PORT = 3100;
server.listen(PORT, () => {
  console.log(`盘古 Dashboard: http://localhost:${PORT}`);
});
