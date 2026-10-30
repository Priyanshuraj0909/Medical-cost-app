'use strict';
const $ = selector => document.querySelector(selector);
const form = $('#estimate-form');
const error = $('#error');
const submit = $('#submit');
const displayCurrency = {
  currency: 'INR', locale: 'en-IN', conversion_applied: false,
  note: 'Amounts are displayed as Indian rupees for this demo without exchange-rate conversion. This display choice does not establish the training dataset’s currency.',
};
const format = value => new Intl.NumberFormat(displayCurrency.locale, { style: 'currency', currency: displayCurrency.currency, maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(value);
const labels = {
  age: 'Age', gender: 'Gender', gender_raw: 'Gender', bmi: 'BMI', smoker: 'Smoking status', smoker_raw: 'Smoking status',
  diabetes: 'Diabetes', hypertension: 'Hypertension', heart_disease: 'Heart disease', asthma: 'Asthma',
  physical_activity_level: 'Physical activity', physical_activity_level_raw: 'Physical activity', daily_steps: 'Daily steps',
  sleep_hours: 'Sleep hours', stress_level: 'Stress level', doctor_visits_per_year: 'Doctor visits',
  hospital_admissions: 'Hospital admissions', medication_count: 'Medications', insurance_type: 'Insurance type',
  insurance_type_raw: 'Insurance type', previous_year_cost: 'Previous year’s cost', city_type_Semi_Urban: 'Semi-urban location',
  city_type_Urban: 'Urban location', city: 'Location', out_of_pocket_frac: 'Out-of-pocket fraction',
  insurance_coverage_frac: 'Insurance coverage', height_cm: 'Height', weight_kg: 'Weight',
};
// Profiles and comparisons are deliberately kept in memory, never localStorage.
let current = null;
let baseline = null;
let busy = false;
const syncInsurance = () => {
  const uninsured = $('#insurance-type').value === 'no_insurance';
  if (uninsured) $('#coverage-percent').value = '0';
  $('#coverage-percent').disabled = busy || uninsured;
};
const invalidate = () => {
  current = null;
  for (const id of ['result', 'explanation', 'warnings', 'comparison']) $(`#${id}`).hidden = true;
  $('#result-heading').textContent = 'Ready for a fresh estimate';
  $('#result-description').textContent = baseline ? 'A comparison is kept. Change your profile and calculate again.' : 'Calculate again to use your current details.';
  error.hidden = true;
};
form.addEventListener('input', invalidate);
form.addEventListener('change', () => { syncInsurance(); invalidate(); });
$('#example').addEventListener('click', () => { form.reset(); syncInsurance(); invalidate(); });

function comparison() {
  $('#comparison').hidden = true;
  $('#baseline-status').hidden = !baseline;
  if (!baseline) return;
  $('#baseline-message').textContent = `Kept estimate: ${format(baseline.result.predicted_medical_cost)}. Change the form and calculate to compare.`;
  if (!current) return;
  if (baseline.result.model_version !== current.result.model_version || baseline.result.currency !== current.result.currency) {
    $('#baseline-message').textContent = 'The model or currency changed. Clear the kept estimate before comparing.';
    return;
  }
  $('#baseline-amount').textContent = format(baseline.result.predicted_medical_cost);
  $('#current-amount').textContent = format(current.result.predicted_medical_cost);
  const delta = current.result.predicted_medical_cost - baseline.result.predicted_medical_cost;
  $('#difference').textContent = delta === 0 ? 'The annual estimates are equal.' : `${format(Math.abs(delta))} ${delta > 0 ? 'higher' : 'lower'} per year (INR display).`;
  const changes = $('#changed-fields');
  changes.replaceChildren();
  for (const [key, value] of Object.entries(current.profile)) {
    if (value === baseline.profile[key]) continue;
    const li = document.createElement('li');
    li.textContent = `${labels[key] || key}: ${baseline.profile[key]} → ${value}`;
    changes.append(li);
  }
  if (!changes.children.length) {
    const li = document.createElement('li'); li.textContent = 'Both profiles use the same inputs.'; changes.append(li);
  }
  $('#comparison').hidden = false;
}
$('#pin').addEventListener('click', () => {
  if (!current) return;
  baseline = structuredClone(current);
  comparison();
});
$('#clear-baseline').addEventListener('click', () => { baseline = null; comparison(); });
$('#download').addEventListener('click', () => {
  if (!current) return;
  const summary = {
    generated_at: current.generated_at,
    display_currency: displayCurrency,
    estimate: current.result,
    comparison: baseline ? { kept_estimate: baseline.result, current_estimate: current.result } : null,
    note: 'Educational model estimate, not a bill or insurance quote. Monthly equivalent is annual cost divided by twelve. Raw profile inputs are omitted from this file.',
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = 'careestimate-summary.json';
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

function render(result) {
  $('#amount').textContent = format(result.predicted_medical_cost);
  $('#monthly').textContent = format(result.predicted_medical_cost / 12);
  $('#currency-unit').textContent = 'estimated annual cost · Indian rupees (INR display)';
  renderDatasetStatus(result.dataset_status);
  $('#model-version').textContent = `LightGBM · model ${result.model_version}`;
  $('#result-heading').textContent = 'Your annual cost estimate';
  $('#result-description').textContent = 'Based on the profile you provided. Review the model’s limits below.';
  $('#uncertainty').textContent = result.uncertainty_note;
  const interval = result.prediction_interval;
  $('#interval').textContent = interval ? `${Math.round(interval.nominal_coverage * 100)}% prediction interval: ${format(interval.lower)}–${format(interval.upper)}. Measured test coverage: ${(interval.measured_test_coverage * 100).toFixed(1)}%.` : '';
  $('#base-value').textContent = `Model starting value: ${format(result.explanation.base_value)}.`;
  const list = $('#factors'); list.replaceChildren();
  const top = result.explanation.contributions.slice(0, 5);
  const maximum = Math.max(...top.map(item => Math.abs(item.contribution)), 1);
  for (const item of top) {
    const li = document.createElement('li');
    const row = document.createElement('div'); row.className = 'factor-label';
    const name = document.createElement('span'); name.textContent = labels[item.feature] || item.feature;
    const value = document.createElement('strong'); value.textContent = `${item.contribution >= 0 ? 'Higher' : 'Lower'} ${format(Math.abs(item.contribution))}`;
    row.append(name, value);
    const track = document.createElement('div'); track.className = 'factor-track'; track.setAttribute('aria-hidden', 'true');
    const bar = document.createElement('div'); bar.className = `factor-bar${item.contribution < 0 ? ' negative' : ''}`;
    // Width is finite numeric data, never HTML from an API response.
    bar.style.width = `${Math.abs(item.contribution) / maximum * 100}%`;
    track.append(bar); li.append(row, track); list.append(li);
  }
  const warnings = $('#warning-list'); warnings.replaceChildren();
  for (const message of result.warnings) { const li = document.createElement('li'); li.textContent = message; warnings.append(li); }
  $('#warnings').hidden = !result.warnings.length;
  $('#result').hidden = false; $('#explanation').hidden = false;
  comparison();
}

function renderDatasetStatus(status) {
  const notes = [displayCurrency.note, ...(status?.notes || ['Dataset documentation could not be loaded. Currency and cost definition have not been confirmed.'])];
  const details = $('#dataset-details');
  details.replaceChildren();
  for (const message of notes) {
    const item = document.createElement('li'); item.textContent = message; details.append(item);
  }
  const missing = status?.missing_details;
  const note = !status ? 'INR display for this demo; no currency conversion is applied. Dataset documentation could not be loaded.'
    : missing.includes('currency') && missing.includes('cost_definition') ? 'INR display for this demo; no currency conversion is applied. Original currency and total versus out-of-pocket cost definition are not documented.'
    : missing.includes('currency') ? 'INR display for this demo; no currency conversion is applied. Original training currency is not documented.'
    : missing.includes('cost_definition') ? 'Demo estimate. Total versus out-of-pocket cost definition is not documented.'
    : missing.includes('source') ? 'Demo estimate. The original dataset source is not documented.'
    : 'Model estimate. See dataset details for its scope and limitations.';
  $('#dataset-note').textContent = note;
  $('#scope-note').textContent = 'For adults aged 18–89. Amounts use Indian rupee formatting for this demo; no currency conversion is applied.';
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (busy) return;
  invalidate();
  const payload = {};
  for (const input of form.querySelectorAll('input, select')) {
    payload[input.name] = input.type === 'checkbox' ? Number(input.checked) : input.type === 'number' ? Number(input.value) : input.value;
  }
  payload.insurance_coverage_frac = payload.coverage_percent / 100;
  delete payload.coverage_percent;
  busy = true; submit.disabled = true; submit.textContent = 'Calculating…';
  form.setAttribute('aria-busy', 'true');
  form.querySelectorAll('input, select, #example').forEach(element => element.disabled = true);
  try {
    const response = await fetch('/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: AbortSignal.timeout(30000) });
    const data = await response.json();
    if (!response.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map(item => `${labels[item.loc.at(-1)] || 'Profile'}: ${item.msg}`).join('; ') : data.detail;
      throw new Error(detail || 'Unable to calculate your estimate. Please try again.');
    }
    if (!Number.isFinite(data.predicted_medical_cost) || data.predicted_medical_cost < 0) throw new Error('The service returned an invalid estimate.');
    current = { result: data, profile: payload, generated_at: new Date().toISOString() };
    render(data);
    if (window.innerWidth < 750 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) $('.result-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (failure) {
    invalidate();
    error.textContent = failure.name === 'TimeoutError' ? 'The request took too long. Please try again.' : failure instanceof TypeError ? 'Could not connect to the prediction service. Please try again.' : failure.message;
    error.hidden = false;
    $('#result-heading').textContent = 'Estimate unavailable';
    $('#result-description').textContent = 'Check your details and try again.';
  } finally {
    busy = false; submit.disabled = false; submit.textContent = 'Calculate my estimate ↗'; form.removeAttribute('aria-busy');
    form.querySelectorAll('input, select, #example').forEach(element => element.disabled = false);
    syncInsurance();
  }
});
syncInsurance();
fetch('/model-info').then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(info => {
  renderDatasetStatus(info.dataset_status);
  $('#model-status').textContent = `Model ${info.model_version}. ${info.validation_status}`;
}).catch(() => { $('#model-status').textContent = 'Model information is unavailable. See the project documentation for known limitations.'; });
