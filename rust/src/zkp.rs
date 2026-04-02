/*
 * This file is licensed under the Affero General Public License (AGPL) version 3.
 *
 * Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
 *
 * See the GNU Affero General Public License for more details:
 * <https://www.gnu.org/licenses/agpl-3.0.html>.
 */

use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, Error};
use pyo3::prelude::*;
use pythonize::{depythonize, pythonize};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZkpVerifyRequest {
    pub proof: Value,
    pub public_signals: Value,
    pub expected_did_uri: String,
    pub expected_xrpl_address: String,
    pub expected_credential_id: String,
    pub expected_e2ee_pubkey_commitment: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZkpVerifyResult {
    pub valid: bool,
    pub verified_at: i64,
    pub reason: Option<String>,
}

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

pub fn verify_zkp_binding(request: &ZkpVerifyRequest) -> Result<ZkpVerifyResult, Error> {
    if request.expected_did_uri.is_empty()
        || request.expected_xrpl_address.is_empty()
        || request.expected_credential_id.is_empty()
        || request.expected_e2ee_pubkey_commitment.is_empty()
    {
        return Err(anyhow!("expected verification parameters cannot be empty"));
    }

    let signals = request
        .public_signals
        .as_object()
        .ok_or_else(|| anyhow!("public_signals must be a JSON object"))?;
    let proof = request
        .proof
        .as_object()
        .ok_or_else(|| anyhow!("proof must be a JSON object"))?;

    let signal_did = signals
        .get("did_uri")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let signal_address = signals
        .get("xrpl_address")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let signal_credential = signals
        .get("credential_id")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let signal_commitment = signals
        .get("e2ee_pubkey_commitment")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let proof_subject = proof
        .get("subject")
        .and_then(Value::as_str)
        .unwrap_or(signal_address);

    let valid = signal_did == request.expected_did_uri
        && signal_address == request.expected_xrpl_address
        && signal_credential == request.expected_credential_id
        && signal_commitment == request.expected_e2ee_pubkey_commitment
        && proof_subject == request.expected_xrpl_address;

    Ok(ZkpVerifyResult {
        valid,
        verified_at: now_ms(),
        reason: if valid {
            None
        } else {
            Some("proof or public signals did not match expected DID/credential binding".to_string())
        },
    })
}

#[pyfunction(name = "verify_zkp_binding")]
fn py_verify_zkp_binding(py: Python<'_>, request: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
    let request: ZkpVerifyRequest = depythonize(request)?;
    let out = verify_zkp_binding(&request)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(pythonize(py, &out)?.unbind())
}

pub fn register_module(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    let child_module = PyModule::new(py, "zkp")?;
    child_module.add_function(wrap_pyfunction!(py_verify_zkp_binding, &child_module)?)?;

    m.add_submodule(&child_module)?;

    let modules = py.import("sys")?.getattr("modules")?;
    modules.set_item("textrp_briij.synapse_rust.zkp", &child_module)?;
    modules.set_item("synapse.synapse_rust.zkp", &child_module)?;
    Ok(())
}
