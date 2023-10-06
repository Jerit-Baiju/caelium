var protocol = 'ws';
var domain = window.location.host
if (debug == 'pro') {
  protocol = 'wss';
}
var websocketURL = protocol + '://' + domain + '/ws/socket-server/';
const chatSocket = new WebSocket(websocketURL)
function change_state(state) {
  chatSocket.send(JSON.stringify({ 'type': 'status', 'content': state }))
  console.log('state')
}
window.onblur = () => {
  change_state('offline')
}
window.onfocus = () => {
  change_state('online')
}
window.onload = () => {
  change_state('online')
}