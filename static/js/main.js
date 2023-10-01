var protocol = 'ws';
var domain = window.location.host;
if (domain.includes('jerit.in')) {
  protocol = 'wss';
}
var websocketURL = protocol + '://' + domain + '/ws/socket-server/';
const chatSocket = new WebSocket(websocketURL)
window.onblur = () => {
  chatSocket.send(JSON.stringify({'type':'status', 'content': 'offline'}))
}
window.onfocus = () => {
  chatSocket.send(JSON.stringify({'type': 'status', 'content': 'online'}))
}