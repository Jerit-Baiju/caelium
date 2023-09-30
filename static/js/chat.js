let url = `${ws}://${window.location.host}/ws/socket-server/`
const chatSocket = new WebSocket(url)
let form = document.getElementById('form')

chatSocket.onmessage = (e) => {
  let data = JSON.parse(e.data)
  console.log(data)
  if (data['type'] == 'message') {
    if (data['user'] == user) {
      var my_msg = $(
        `<div class="media mb-1 justify-content-end d-flex">
          <div class="media-body text-right ps-5">
            <div class="alert alert-primary" role="alert">${data['data']}</div>
          </div>
          <div class="img-fluid">
            <img class="ms-2 mt-1 chat-user-profile" src="${user_avatar}" alt="">
          </div>
        </div>`
      );
    }
    else if (data['user'] == partner) {
      var my_msg = $(
        `<div class="media mb-1 d-flex">
          <div class="img-fluid">
            <img class="me-2 mt-1 chat-user-profile" src="${partner_avatar}" alt="">
          </div>
          <div class="media-body pe-5">
            <div class="alert alert-success" role="alert">${data['data']}</div>
          </div>
        </div>`
      );
    }
    $('#scrollable').append(my_msg);
    scroll()
  }

}
chatSocket.onclose = function (e) {
  console.error('Chat socket closed unexpectedly');
};

form.addEventListener('submit', (e) => {
  e.preventDefault()
  let message = e.target.message.value
  chatSocket.send(JSON.stringify({ 'message': message }))
  form.reset()
})
function scroll() {
  var scrollingDiv = document.getElementById("scrollable");
  scrollingDiv.scrollTop = scrollingDiv.scrollHeight;
}
scroll()
window.scrollTo(0, document.body.scrollHeight);