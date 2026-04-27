use super::{DbConnection, DbPool};
use diesel::prelude::*;

use crate::shared::domain::DomainError;
use crate::shared::persistence::db::models::ReportTagModel;
use crate::shared::persistence::db::schema::report_tag;

#[derive(Clone)]
pub struct ReportTagRepository {}

impl ReportTagRepository {
    pub fn new(_pool: DbPool) -> Self {
        Self {}
    }

    pub fn insert_all(
        &self,
        conn: &mut DbConnection,
        report_id: i32,
        pairs: &[(i32, i32)],
    ) -> Result<(), DomainError> {
        if pairs.is_empty() {
            return Ok(());
        }
        let rows: Vec<ReportTagModel> = pairs
            .iter()
            .map(|(key_id, value_id)| ReportTagModel {
                report_id,
                key_id: *key_id,
                value_id: *value_id,
            })
            .collect();
        diesel::insert_into(report_tag::table)
            .values(&rows)
            .on_conflict((report_tag::report_id, report_tag::key_id))
            .do_nothing()
            .execute(conn)
            .map_err(|e| DomainError::Database(e.to_string()))?;
        Ok(())
    }
}
