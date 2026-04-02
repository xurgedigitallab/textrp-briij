/*
 * This file is licensed under the Affero General Public License (AGPL) version 3.
 *
 * Copyright (C) 2026 xurgedigitallab / TextRP-Briij contributors
 *
 * See the GNU Affero General Public License for more details:
 * <https://www.gnu.org/licenses/agpl-3.0.html>.
 */

use std::collections::HashSet;
use std::env;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, Context, Error};
use lazy_static::lazy_static;
use pyo3::prelude::*;
use pythonize::{depythonize, pythonize};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

lazy_static! {
    static ref ISSUED_CREDENTIALS: Mutex<HashSet<String>> = Mutex::new(HashSet::new());
    static ref REVOKED_CREDENTIALS: Mutex<HashSet<String>> = Mutex::new(HashSet::new());
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CredentialCreateTransaction {
    pub subject: String,
    pub did_uri: String,
    pub matrix_user_id: String,
    pub e2ee_pubkey_commitment: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CredentialDeleteTransaction {
    pub credential_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CredentialLedgerEntry {
    pub credential_id: String,
    pub subject: String,
    pub did_uri: String,
    pub status: String,
    pub issued_at: i64,
    pub tx_hash: String,
    pub network: String,
    pub claims: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CredentialDeleteResult {
    pub credential_id: String,
    pub status: String,
}

fn validate_subject(subject: &str) -> Result<(), Error> {
    if !subject.starts_with('r') || subject.len() < 25 {
        return Err(anyhow!("invalid XRPL account"));
    }
    Ok(())
}

fn hash_hex(input: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    format!("{:x}", hasher.finalize())
}

fn now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as i64)
        .unwrap_or(0)
}

fn maybe_probe_testnet(subject: &str) -> Result<(), Error> {
    let url = env::var("TEXTRP_CREDENTIAL_TESTNET_RPC_URL")
        .ok()
        .filter(|v| !v.is_empty())
        .or_else(|| env::var("TEXTRP_DID_TESTNET_RPC_URL").ok().filter(|v| !v.is_empty()));

    let Some(url) = url else {
        return Ok(());
    };

    let payload = format!(
        r#"{{"method":"account_info","params":[{{"account":"{subject}","ledger_index":"validated","strict":true}}]}}"#
    );

    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .context("creating tokio runtime for credential testnet probe")?;

    runtime.block_on(async {
        let response = reqwest::Client::new()
            .post(url)
            .header("content-type", "application/json")
            .body(payload)
            .send()
            .await
            .context("sending account_info request to XRPL testnet")?;

        if !response.status().is_success() {
            return Err(anyhow!(
                "XRPL testnet request failed with status {}",
                response.status()
            ));
        }
        Ok::<(), Error>(())
    })?;

    Ok(())
}

pub fn submit_credential_create(
    tx: &CredentialCreateTransaction,
) -> Result<CredentialLedgerEntry, Error> {
    validate_subject(&tx.subject)?;
    if !tx.did_uri.starts_with("did:xrpl:testnet:") {
        return Err(anyhow!("did_uri must start with did:xrpl:testnet:"));
    }
    if tx.e2ee_pubkey_commitment.is_empty() {
        return Err(anyhow!("e2ee_pubkey_commitment cannot be empty"));
    }

    maybe_probe_testnet(&tx.subject)?;

    let claims = json!({
        "matrix_user_id": tx.matrix_user_id,
        "did_uri": tx.did_uri,
        "e2ee_pubkey_commitment": tx.e2ee_pubkey_commitment
    });
    let digest_input = format!(
        "{}|{}|{}|{}",
        tx.subject, tx.did_uri, tx.matrix_user_id, tx.e2ee_pubkey_commitment
    );
    let credential_id = format!("cred-{}", &hash_hex(&digest_input)[..24]);
    let tx_hash = hash_hex(&format!("tx:{digest_input}"));
    let issued_at = now_ms();

    ISSUED_CREDENTIALS
        .lock()
        .map_err(|_| anyhow!("issued credential lock poisoned"))?
        .insert(credential_id.clone());
    REVOKED_CREDENTIALS
        .lock()
        .map_err(|_| anyhow!("revoked credential lock poisoned"))?
        .remove(&credential_id);

    Ok(CredentialLedgerEntry {
        credential_id,
        subject: tx.subject.clone(),
        did_uri: tx.did_uri.clone(),
        status: "issued".to_string(),
        issued_at,
        tx_hash,
        network: "xrpl-testnet".to_string(),
        claims,
    })
}

pub fn submit_credential_delete(
    tx: &CredentialDeleteTransaction,
) -> Result<CredentialDeleteResult, Error> {
    if tx.credential_id.is_empty() {
        return Err(anyhow!("credential_id cannot be empty"));
    }
    REVOKED_CREDENTIALS
        .lock()
        .map_err(|_| anyhow!("revoked credential lock poisoned"))?
        .insert(tx.credential_id.clone());
    Ok(CredentialDeleteResult {
        credential_id: tx.credential_id.clone(),
        status: "revoked".to_string(),
    })
}

pub fn verify_credential(credential_id: &str) -> Result<bool, Error> {
    if credential_id.is_empty() {
        return Err(anyhow!("credential_id cannot be empty"));
    }
    if REVOKED_CREDENTIALS
        .lock()
        .map_err(|_| anyhow!("revoked credential lock poisoned"))?
        .contains(credential_id)
    {
        return Ok(false);
    }
    if ISSUED_CREDENTIALS
        .lock()
        .map_err(|_| anyhow!("issued credential lock poisoned"))?
        .contains(credential_id)
    {
        return Ok(true);
    }
    Ok(credential_id.starts_with("cred-"))
}

#[pyfunction(name = "submit_credential_create")]
fn py_submit_credential_create(
    py: Python<'_>,
    tx: &Bound<'_, PyAny>,
) -> PyResult<Py<PyAny>> {
    let tx: CredentialCreateTransaction = depythonize(tx)?;
    let out = submit_credential_create(&tx)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(pythonize(py, &out)?.unbind())
}

#[pyfunction(name = "submit_credential_delete")]
fn py_submit_credential_delete(
    py: Python<'_>,
    tx: &Bound<'_, PyAny>,
) -> PyResult<Py<PyAny>> {
    let tx: CredentialDeleteTransaction = depythonize(tx)?;
    let out = submit_credential_delete(&tx)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(pythonize(py, &out)?.unbind())
}

#[pyfunction(name = "verify_credential")]
fn py_verify_credential(credential_id: &str) -> PyResult<bool> {
    verify_credential(credential_id)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

pub fn register_module(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    let child_module = PyModule::new(py, "credential")?;
    child_module.add_function(wrap_pyfunction!(py_submit_credential_create, &child_module)?)?;
    child_module.add_function(wrap_pyfunction!(py_submit_credential_delete, &child_module)?)?;
    child_module.add_function(wrap_pyfunction!(py_verify_credential, &child_module)?)?;

    m.add_submodule(&child_module)?;

    let modules = py.import("sys")?.getattr("modules")?;
    modules.set_item("textrp_briij.synapse_rust.credential", &child_module)?;
    modules.set_item("synapse.synapse_rust.credential", &child_module)?;
    Ok(())
}
