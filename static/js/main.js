var protocol = 'ws';
var user_state = 'offline'
var domain = window.location.host
if (debug == 'pro') {
  protocol = 'wss';
}
var websocketURL = protocol + '://' + domain + '/ws/socket-server/';
const chatSocket = new WebSocket(websocketURL)
function change_state(state){
  if (state != user_state){
  chatSocket.send(JSON.stringify({'type': 'status', 'content': state}))
  }
}
change_state('online')
window.onblur = () => {
  change_state('offline')
}
window.onfocus = () => {
  change_state('online')
}