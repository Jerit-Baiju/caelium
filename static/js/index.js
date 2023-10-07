function updateDaysCount() {
  const currentDate = new Date();
  const timeDifference = currentDate - targetDate;
  const days = Math.floor(timeDifference / (1000 * 60 * 60 * 24));
  const years = Math.floor(days / 365);
  const remainingDays = days % 365;
  const months = Math.floor(remainingDays / 30);
  const remainingMonths = remainingDays % 30;
  document.getElementById('totalDays').textContent = `Day: ${days}`;
  document.getElementById('daysCount').textContent = `${years} years, ${months} months, ${remainingMonths} days`;
}
updateDaysCount();
function updatePartnerStatus(status) {
  const partnerStatusElement = document.getElementById('partnerStatus');
  if (status == true || status == 'online') {
    partnerStatusElement.innerHTML = `${partner} is <span class="text-success">online</span>`;
  } else {
    partnerStatusElement.innerHTML = `${partner} is <span class="text-danger">offline</span>`;
  }
}
updatePartnerStatus(partner_status);
chatSocket.onmessage = (e) => {
  data = JSON.parse(e.data)
  console.log(data)
  if (data['type'] == 'status' & data['user'] == partner_email) {
    updatePartnerStatus(data['status'])
  }
}