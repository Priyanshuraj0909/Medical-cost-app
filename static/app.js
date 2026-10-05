const form = document.querySelector('#estimate-form');
const error = document.querySelector('#error');
const submit = document.querySelector('#submit');
const format = value => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(value);
const invalidate = () => {
  document.querySelector('#result').hidden = true;
  document.querySelector('#result-heading').textContent = 'Ready for a fresh estimate';
  document.querySelector('#result-description').textContent = 'Calculate again to use your current details.';
  error.hidden = true;
};
form.addEventListener('input', invalidate);
form.addEventListener('change', invalidate);
document.querySelector('#example').addEventListener('click', () => { form.reset(); invalidate(); });
form.addEventListener('submit', async event => {
  event.preventDefault();
  error.hidden = true;
  document.querySelector('#result').hidden = true;
  const payload = {};
  for (const input of form.querySelectorAll('input, select')) {
    payload[input.name] = input.type === 'checkbox' ? Number(input.checked) : input.type === 'number' ? Number(input.value) : input.value;
  }
  payload.insurance_coverage_frac = payload.coverage_percent / 100;
  delete payload.coverage_percent;
  submit.disabled = true;
  submit.textContent = 'Calculating…';
  form.querySelectorAll('input, select, #example').forEach(element => element.disabled = true);
  try {
    const response = await fetch('/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: AbortSignal.timeout(30000) });
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join('; ') : data.detail;
      throw new Error(detail || 'Unable to calculate your estimate. Please try again.');
    }
    if (!Number.isFinite(data.predicted_medical_cost) || data.predicted_medical_cost < 0) throw new Error('The service returned an invalid estimate.');
    document.querySelector('#amount').textContent = format(data.predicted_medical_cost);
    document.querySelector('#monthly').textContent = format(data.predicted_medical_cost / 12);
    document.querySelector('#result-heading').textContent = 'Your annual cost estimate';
    document.querySelector('#result-description').textContent = 'Based on the health, lifestyle, and insurance details you provided.';
    document.querySelector('#result').hidden = false;
    if (window.innerWidth < 750) document.querySelector('.result-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (failure) {
    error.textContent = failure.name === 'TimeoutError' ? 'The request took too long. Please try again.' : failure instanceof TypeError ? 'Could not connect to the prediction service. Please try again.' : failure.message;
    error.hidden = false;
    document.querySelector('#result-heading').textContent = 'Estimate unavailable';
    document.querySelector('#result-description').textContent = 'Check your details and try again.';
  } finally {
    submit.disabled = false;
    submit.innerHTML = 'Calculate my estimate <span>↗</span>';
    form.querySelectorAll('input, select, #example').forEach(element => element.disabled = false);
  }
});
