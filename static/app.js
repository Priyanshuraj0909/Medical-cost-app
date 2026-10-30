'use strict';
const $ = selector => document.querySelector(selector);
const i18n = window.CareI18n;
const t = (key, values) => i18n.t(key, values);
const charts = window.CareCharts;
const form = $('#estimate-form');
const error = $('#error');
const submit = $('#submit');
const displayCurrency = {
  currency: 'INR', locale: 'en-IN', conversion_applied: false,
  note: 'Amounts are displayed as Indian rupees for this demo without exchange-rate conversion. This display choice does not establish the training dataset’s currency.',
};
const format = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
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
const label = key => t(labels[key] || key);
let current = null;
let baseline = null;
let scenario = null;
let busy = false;
let scenarioBusy = false;
let scenarioController = null;
let step = 0;
let allFields = false;
let modelInfo = null;
const fieldsets = [...form.querySelectorAll('[data-form-step]')];

function showStep(index, focus = false) {
  step = Math.max(0, Math.min(2, index));
  fieldsets.forEach((fieldset, position) => fieldset.hidden = !allFields && position !== step);
  document.querySelectorAll('[data-step]').forEach(button => {
    if (Number(button.dataset.step) === step) button.setAttribute('aria-current', 'step');
    else button.removeAttribute('aria-current');
    button.disabled = busy;
  });
  $('#step-status').textContent = t('Step {step} of 3', { step: step + 1 });
  $('#view-all').textContent = t(allFields ? 'Use guided steps' : 'Show all fields');
  $('#previous').hidden = allFields || step === 0;
  $('#next').hidden = allFields || step === 2;
  submit.hidden = !allFields && step !== 2;
  if (focus) fieldsets[step].querySelector('input, select')?.focus();
}
function validateField(input) {
  const old = input.parentElement.querySelector('.field-error');
  old?.remove(); input.removeAttribute('aria-invalid'); input.removeAttribute('aria-describedby');
  if (input.disabled || input.validity.valid) return true;
  let message = t('Please enter a valid value.');
  if (input.validity.valueMissing) message = t('Please enter a value.');
  else if (input.validity.rangeUnderflow) message = t('Value must be at least {value}.', { value: input.min });
  else if (input.validity.rangeOverflow) message = t('Value must be no more than {value}.', { value: input.max });
  else if (input.validity.stepMismatch) message = t('Please enter a whole number.');
  const text = document.createElement('span'); text.className = 'field-error'; text.id = `error-${input.name}`; text.textContent = message;
  input.parentElement.append(text); input.setAttribute('aria-invalid', 'true'); input.setAttribute('aria-describedby', text.id);
  return false;
}
function validate(fields) {
  const invalid = [...fields].filter(input => !validateField(input));
  if (!invalid.length) return true;
  const first = invalid[0]; showStep(Number(first.closest('[data-form-step]').dataset.formStep)); first.focus();
  error.textContent = t('Please review the highlighted fields.'); error.hidden = false;
  return false;
}
$('#next').addEventListener('click', () => { if (validate(fieldsets[step].querySelectorAll('input, select'))) showStep(step + 1, true); });
$('#previous').addEventListener('click', () => showStep(step - 1, true));
$('#view-all').addEventListener('click', () => { allFields = !allFields; showStep(step); });
document.querySelectorAll('[data-step]').forEach(button => button.addEventListener('click', () => {
  const target = Number(button.dataset.step);
  if (target <= step || validate(fieldsets[step].querySelectorAll('input, select'))) showStep(target, true);
}));
function syncInsurance() {
  const uninsured = $('#insurance-type').value === 'no_insurance';
  if (uninsured) $('#coverage-percent').value = '0';
  $('#coverage-percent').disabled = busy || uninsured;
}
function resetScenario() {
  scenarioController?.abort(); scenarioController = null; scenarioBusy = false; scenario = null;
  $('#scenario-result').hidden = true; $('#scenario-error').hidden = true;
  $('#scenario-calculate').disabled = false; $('#scenario-calculate').textContent = t('Compare scenario');
  $('#scenario-feature').disabled = false; $('#scenario-value').disabled = false;
  $('#scenario-summary').textContent = t('Calculate a scenario to compare it with your current estimate.');
  charts.destroy('scenario-chart');
}
function invalidate() {
  current = null; resetScenario(); charts.clear();
  for (const id of ['result', 'explanation', 'warnings', 'comparison', 'scenario-panel', 'insights']) $(`#${id}`).hidden = true;
  $('#print-report').replaceChildren(); $('#print-report').hidden = true;
  $('#result-heading').textContent = t('Ready for a fresh estimate');
  $('#result-description').textContent = t(baseline ? 'A comparison is kept. Change your profile and calculate again.' : 'Calculate again to use your current details.');
  error.hidden = true;
}
form.addEventListener('input', event => { invalidate(); if (event.target.matches('input, select')) validateField(event.target); });
form.addEventListener('change', () => { syncInsurance(); invalidate(); });
$('#example').addEventListener('click', () => {
  form.reset(); form.querySelectorAll('.field-error').forEach(node => node.remove());
  form.querySelectorAll('[aria-invalid]').forEach(node => { node.removeAttribute('aria-invalid'); node.removeAttribute('aria-describedby'); });
  syncInsurance(); invalidate(); showStep(0);
});
function difference(value) {
  return value === 0 ? t('The annual estimates are equal.') : t(value > 0 ? '{amount} higher per year (INR display).' : '{amount} lower per year (INR display).', { amount: format(Math.abs(value)) });
}
function warningText(message) {
  const suffix = ' is outside the recorded training range; this estimate may be unreliable.';
  if (message.endsWith(suffix)) {
    const name = message.slice(0, -suffix.length);
    const key = Object.keys(labels).find(key => labels[key].toLowerCase() === name.toLowerCase() || key.toLowerCase() === name.toLowerCase().replaceAll(' ', '_'));
    return t('{field} is outside the recorded training range; this estimate may be unreliable.', { field: key ? label(key) : name });
  }
  return t(message);
}
function listMessages(id, messages, translate = t) {
  const list = $(id); list.replaceChildren();
  for (const message of messages) { const li = document.createElement('li'); li.textContent = translate(message); list.append(li); }
}
function comparable() {
  return baseline && current && baseline.result.model_version === current.result.model_version && baseline.result.currency === current.result.currency;
}
function comparison() {
  $('#comparison').hidden = true; charts.destroy('comparison-chart');
  $('#baseline-status').hidden = !baseline;
  if (!baseline) return;
  $('#baseline-message').textContent = t('Kept estimate: {amount}. Change the form and calculate to compare.', { amount: format(baseline.result.predicted_medical_cost) });
  if (!current) return;
  if (!comparable()) { $('#baseline-message').textContent = t('The model or currency changed. Clear the kept estimate before comparing.'); return; }
  const values = [baseline.result.predicted_medical_cost, current.result.predicted_medical_cost];
  $('#baseline-amount').textContent = format(values[0]); $('#current-amount').textContent = format(values[1]);
  $('#difference').textContent = difference(values[1] - values[0]);
  const changes = $('#changed-fields'); changes.replaceChildren();
  for (const [key, value] of Object.entries(current.profile)) {
    if (value === baseline.profile[key]) continue;
    const li = document.createElement('li'); li.textContent = `${label(key)}: ${baseline.profile[key]} → ${value}`; changes.append(li);
  }
  if (!changes.children.length) { const li = document.createElement('li'); li.textContent = t('Both profiles use the same inputs.'); changes.append(li); }
  $('#comparison').hidden = false;
  charts.bar('comparison-chart', [t('Kept estimate'), t('Current estimate')], values);
}
$('#pin').addEventListener('click', () => { if (current) { baseline = structuredClone(current); comparison(); } });
$('#clear-baseline').addEventListener('click', () => { baseline = null; comparison(); });
$('#download').addEventListener('click', () => {
  if (!current) return;
  const summary = {
    generated_at: current.generated_at, language: i18n.language, display_currency: displayCurrency, estimate: current.result,
    comparison: comparable() ? { kept_estimate: baseline.result, current_estimate: current.result } : null,
    scenario: scenario ? { estimate: scenario.result, changed_factor: scenario.feature, scenario_value: scenario.value } : null,
    note: t('Educational model estimate, not a bill or insurance quote. Monthly equivalent is annual cost divided by twelve. Raw profile inputs are omitted from this file.'),
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(summary, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = 'careestimate-summary.json';
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
function renderDatasetStatus(status) {
  listMessages('#dataset-details', [displayCurrency.note, ...(status?.notes || ['Dataset documentation could not be loaded. Currency and cost definition have not been confirmed.'])]);
  const missing = status?.missing_details || ['currency', 'source', 'cost_definition'];
  const note = missing.includes('currency') && missing.includes('cost_definition') ? 'INR display for this demo; no currency conversion is applied. Original currency and total versus out-of-pocket cost definition are not documented.'
    : missing.includes('currency') ? 'INR display for this demo; no currency conversion is applied. Original training currency is not documented.'
    : missing.includes('cost_definition') ? 'Demo estimate. Total versus out-of-pocket cost definition is not documented.'
    : missing.includes('source') ? 'Demo estimate. The original dataset source is not documented.'
    : 'Model estimate. See dataset details for its scope and limitations.';
  $('#dataset-note').textContent = t(note);
  $('#scope-note').textContent = t('For adults aged 18–89. Amounts use Indian rupee formatting for this demo; no currency conversion is applied.');
}
function render() {
  if (!current) return;
  const result = current.result;
  $('#amount').textContent = format(result.predicted_medical_cost); $('#monthly').textContent = format(result.predicted_medical_cost / 12);
  $('#currency-unit').textContent = t('estimated annual cost · Indian rupees (INR display)'); renderDatasetStatus(result.dataset_status);
  $('#model-version').textContent = `LightGBM · ${result.model_version}`;
  $('#result-heading').textContent = t('Your annual cost estimate');
  $('#result-description').textContent = t('Based on the profile you provided. Review the model’s limits below.');
  $('#uncertainty').textContent = t(result.uncertainty_note);
  const interval = result.prediction_interval;
  $('#interval').textContent = interval ? t('{coverage}% prediction interval: {lower}–{upper}. Measured test coverage: {measured}%.', { coverage: Math.round(interval.nominal_coverage * 100), lower: format(interval.lower), upper: format(interval.upper), measured: (interval.measured_test_coverage * 100).toFixed(1) }) : '';
  $('#base-value').textContent = t('Model starting value: {amount}.', { amount: format(result.explanation.base_value) });
  const top = result.explanation.contributions.slice(0, 5);
  const list = $('#factors'); list.replaceChildren();
  for (const item of top) {
    const li = document.createElement('li'); const row = document.createElement('div'); row.className = 'factor-label';
    const name = document.createElement('span'); name.textContent = label(item.feature);
    const value = document.createElement('strong'); value.textContent = t(item.contribution >= 0 ? 'Higher {amount}' : 'Lower {amount}', { amount: format(Math.abs(item.contribution)) });
    row.append(name, value); li.append(row); list.append(li);
  }
  listMessages('#warning-list', result.warnings, warningText); $('#warnings').hidden = !result.warnings.length;
  $('#result').hidden = false; $('#explanation').hidden = false; $('#scenario-panel').hidden = false; $('#insights').hidden = false;
  charts.bar('contribution-chart', top.map(item => label(item.feature)), top.map(item => item.contribution), { horizontal: true, signed: true });
  comparison(); if (scenario) renderScenario();
}
async function requestPrediction(payload, signal) {
  const response = await fetch('/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: signal || AbortSignal.timeout(30000) });
  const data = await response.json().catch(() => { throw new Error(t('Unable to calculate your estimate. Please try again.')); });
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(item => `${label(item.loc.at(-1))}: ${t(item.msg)}`).join('; ') : t(data.detail || 'Unable to calculate your estimate. Please try again.');
    throw new Error(detail);
  }
  if (!Number.isFinite(data.predicted_medical_cost) || data.predicted_medical_cost < 0) throw new Error(t('The service returned an invalid estimate.'));
  return data;
}
function failureText(failure) {
  return failure.name === 'TimeoutError' ? t('The request took too long. Please try again.') : failure instanceof TypeError ? t('Could not connect to the prediction service. Please try again.') : failure.message;
}
function setBusy(value) {
  busy = value; submit.disabled = value; submit.textContent = t(value ? 'Calculating…' : 'Calculate my estimate ↗');
  if (value) form.setAttribute('aria-busy', 'true'); else form.removeAttribute('aria-busy');
  form.querySelectorAll('input, select, #example, #previous, #next, #view-all').forEach(element => element.disabled = value);
  syncInsurance(); showStep(step);
}
form.addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  if (!validate(form.querySelectorAll('input, select'))) return;
  // Enter advances a guided step; final-step submission validates every field.
  if (!allFields && step < 2) { showStep(step + 1, true); return; }
  invalidate();
  const payload = {};
  for (const input of form.querySelectorAll('input, select')) payload[input.name] = input.type === 'checkbox' ? Number(input.checked) : input.type === 'number' ? Number(input.value) : input.value;
  payload.insurance_coverage_frac = payload.coverage_percent / 100; delete payload.coverage_percent;
  setBusy(true);
  try {
    const result = await requestPrediction(payload);
    current = { result, profile: payload, generated_at: new Date().toISOString() }; configureScenario(); render();
    if (window.innerWidth < 750) $('.result-card').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
  } catch (failure) {
    invalidate(); error.textContent = failureText(failure); error.hidden = false;
    $('#result-heading').textContent = t('Estimate unavailable'); $('#result-description').textContent = t('Check your details and try again.');
  } finally { setBusy(false); }
});
const scenarioRanges = { hospital_admissions: [0, 6, 1], insurance_coverage_frac: [0, 94, 1], doctor_visits_per_year: [0, 14, 1], daily_steps: [1000, 15000, 500] };
function scenarioValue() { return Number($('#scenario-value').value) / ($('#scenario-feature').value === 'insurance_coverage_frac' ? 100 : 1); }
function updateScenarioValue() {
  $('#scenario-value-label').textContent = `${$('#scenario-value').value}${$('#scenario-feature').value === 'insurance_coverage_frac' ? '%' : ''}`;
}
function configureScenario() {
  resetScenario();
  const key = $('#scenario-feature').value; const [min, max, increment] = scenarioRanges[key]; const input = $('#scenario-value');
  input.min = min; input.max = max; input.step = increment;
  const existing = current?.profile[key] ?? min;
  input.value = key === 'insurance_coverage_frac' ? existing * 100 : Math.min(max, existing + increment);
  updateScenarioValue();
}
$('#scenario-feature').addEventListener('change', configureScenario);
$('#scenario-value').addEventListener('input', () => { resetScenario(); updateScenarioValue(); });
function renderScenario() {
  if (!scenario || !current) return;
  $('#scenario-result').hidden = false;
  $('#scenario-current').textContent = format(current.result.predicted_medical_cost); $('#scenario-amount').textContent = format(scenario.result.predicted_medical_cost);
  $('#scenario-summary').textContent = `${t('Scenario ready: {field} = {value}.', { field: label(scenario.feature), value: scenario.feature === 'insurance_coverage_frac' ? `${scenario.value * 100}%` : scenario.value })} ${t('Your current form was not changed.')}`;
  $('#scenario-difference').textContent = difference(scenario.result.predicted_medical_cost - current.result.predicted_medical_cost);
  listMessages('#scenario-warnings', scenario.result.warnings, warningText);
  charts.bar('scenario-chart', [t('Current estimate'), t('Scenario estimate')], [current.result.predicted_medical_cost, scenario.result.predicted_medical_cost]);
}
$('#scenario-calculate').addEventListener('click', async () => {
  if (!current || scenarioBusy) return;
  const profile = structuredClone(current.profile); const feature = $('#scenario-feature').value; const value = scenarioValue(); profile[feature] = value;
  if (feature === 'insurance_coverage_frac' && profile.insurance_type_raw === 'no_insurance' && value > 0) {
    $('#scenario-error').textContent = t('No insurance requires zero insurance coverage'); $('#scenario-error').hidden = false; return;
  }
  resetScenario(); scenarioBusy = true; scenarioController = new AbortController(); const controller = scenarioController;
  $('#scenario-calculate').disabled = true; $('#scenario-feature').disabled = true; $('#scenario-value').disabled = true;
  $('#scenario-calculate').textContent = t('Calculating…');
  const timeout = setTimeout(() => controller.abort(new DOMException('Timed out', 'TimeoutError')), 30000);
  try {
    const result = await requestPrediction(profile, controller.signal);
    if (controller.signal.aborted || !current) return;
    if (result.model_version !== current.result.model_version || result.currency !== current.result.currency) throw new Error(t('The model changed. Recalculate your main estimate before exploring a scenario.'));
    scenario = { result, feature, value }; renderScenario();
  } catch (failure) {
    if (failure.name !== 'AbortError') { $('#scenario-error').textContent = failureText(failure); $('#scenario-error').hidden = false; }
  } finally {
    clearTimeout(timeout);
    if (scenarioController === controller) {
      scenarioBusy = false; scenarioController = null; $('#scenario-calculate').disabled = false; $('#scenario-feature').disabled = false; $('#scenario-value').disabled = false; $('#scenario-calculate').textContent = t('Compare scenario');
    }
  }
});
function createReport() {
  if (!current) return;
  const report = $('#print-report'); report.replaceChildren(); report.hidden = false;
  function add(tag, text) { const node = document.createElement(tag); node.textContent = text; report.append(node); return node; }
  add('h1', `CareEstimate · ${t('Estimate report')}`);
  add('p', t('Generated: {date}', { date: new Intl.DateTimeFormat(i18n.language === 'hi' ? 'hi-IN' : 'en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(new Date(current.generated_at)) + ' IST' }));
  add('p', t('Model version: {version}', { version: current.result.model_version }));
  add('h2', `${t('Annual estimate')}: ${format(current.result.predicted_medical_cost)}`);
  add('p', `${t('Monthly equivalent')}: ${format(current.result.predicted_medical_cost / 12)}`);
  add('p', t(displayCurrency.note)); add('p', t(current.result.uncertainty_note));
  if (current.result.prediction_interval) add('p', $('#interval').textContent);
  if (comparable()) { add('h2', t('Comparison')); add('p', `${t('Kept estimate')}: ${format(baseline.result.predicted_medical_cost)}`); add('p', $('#difference').textContent); }
  if (scenario) { add('h2', t('Scenario comparison')); add('p', $('#scenario-summary').textContent); add('p', `${t('Scenario estimate')}: ${format(scenario.result.predicted_medical_cost)}`); add('p', $('#scenario-difference').textContent); }
  add('h2', t('Leading model factors')); add('p', $('#base-value').textContent);
  for (const item of current.result.explanation.contributions.slice(0, 5)) add('p', `${label(item.feature)}: ${format(item.contribution)}`);
  add('h2', t('Model limitations'));
  for (const note of current.result.dataset_status.notes) add('p', t(note));
  for (const warning of [...current.result.warnings, ...(scenario?.result.warnings || [])]) add('p', warningText(warning));
  add('p', t('These explain the model’s calculation. They are not causes or guaranteed savings.'));
  add('p', t('Educational model estimate, not a bill or insurance quote. Monthly equivalent is annual cost divided by twelve. Raw profile inputs are omitted from this file.'));
}
$('#print').addEventListener('click', () => { if (current) { createReport(); window.print(); } });
window.addEventListener('beforeprint', createReport);
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $('#theme').setAttribute('aria-pressed', String(theme === 'dark'));
  try { localStorage.setItem('careestimate-theme', theme); } catch { /* Preferences only. */ }
  if (current) render();
}
$('#theme').addEventListener('click', () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
$('#language').addEventListener('change', event => {
  i18n.setLanguage(event.target.value); showStep(step); renderDatasetStatus(current?.result.dataset_status || modelInfo?.dataset_status);
  submit.textContent = t(busy ? 'Calculating…' : 'Calculate my estimate ↗');
  $('#scenario-calculate').textContent = t(scenarioBusy ? 'Calculating…' : 'Compare scenario');
  if (current) render(); else invalidate();
  if (modelInfo) $('#model-status').textContent = t('Model {version}. {status}', { version: modelInfo.model_version, status: t(modelInfo.validation_status) });
  if (!scenario) $('#scenario-summary').textContent = t('Calculate a scenario to compare it with your current estimate.');
  updateConnection();
  form.querySelectorAll('[aria-invalid]').forEach(validateField);
});
function updateConnection() { $('#connection-note').hidden = navigator.onLine; $('#connection-note').textContent = t('Offline: the interface is available, but predictions need an internet connection.'); }
window.addEventListener('online', updateConnection); window.addEventListener('offline', updateConnection);
let installPrompt = null;
window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); installPrompt = event; $('#install').hidden = false; });
$('#install').addEventListener('click', async () => { if (installPrompt) { await installPrompt.prompt(); installPrompt = null; $('#install').hidden = true; } });
window.addEventListener('appinstalled', () => { installPrompt = null; $('#install').hidden = true; });
i18n.apply(); showStep(0); syncInsurance(); updateConnection();
try { applyTheme(localStorage.getItem('careestimate-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')); } catch { applyTheme('light'); }
renderDatasetStatus(null);
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => { /* Predictions work without installation support. */ });
fetch('/model-info', { cache: 'no-store' }).then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(info => {
  modelInfo = info; renderDatasetStatus(current?.result.dataset_status || info.dataset_status);
  $('#model-status').textContent = t('Model {version}. {status}', { version: info.model_version, status: t(info.validation_status) });
}).catch(() => { $('#model-status').textContent = t('Model information is unavailable. See the project documentation for known limitations.'); });
