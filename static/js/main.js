var protocol = 'ws';
var domain = window.location.host;
var user_state = 'offline'
if (debug == 'pro') {
  protocol = 'wss';
}
var websocketURL = protocol + '://' + domain + '/ws/socket-server/';
const chatSocket = new WebSocket(websocketURL);

chatSocket.addEventListener('open', (event) => {
  function change_state(state) {
    if (user_state != state) {
      user_state = state
      chatSocket.send(JSON.stringify({ 'type': 'status', 'content': state }));
    }
  }
  window.onblur = () => {
    change_state('offline');
  };
  window.onfocus = () => {
    change_state('online');
  };
  window.onload = () => {
    change_state('online');
  };
});
chatSocket.addEventListener('error', (error) => {
  console.error('WebSocket error:', error);
});
chatSocket.addEventListener('close', (event) => {
  console.log('WebSocket connection is closed.');
});
