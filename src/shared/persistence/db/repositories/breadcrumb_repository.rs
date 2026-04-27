use super::{DbConnection, DbPool};
use crate::shared::domain::DomainError;
use crate::shared::persistence::db::models::{NewUnwrapBreadcrumbModel, UnwrapBreadcrumbModel};
use crate::shared::persistence::db::schema::unwrap_breadcrumb;
use diesel::prelude::*;

#[derive(Clone)]
pub struct BreadcrumbRepository {}

impl BreadcrumbRepository {
    pub fn new(_pool: DbPool) -> Self {
        Self {}
    }

    pub fn get_or_create(
        &self,
        conn: &mut DbConnection,
        hash: &str,
        timestamp: Option<i64>,
        category_id: Option<i32>,
        type_id: Option<i32>,
        level_id: Option<i32>,
        data: Option<serde_json::Value>,
    ) -> Result<i32, DomainError> {
        if let Some(existing) = unwrap_breadcrumb::table
            .filter(unwrap_breadcrumb::hash.eq(hash))
            .select(UnwrapBreadcrumbModel::as_select())
            .first::<UnwrapBreadcrumbModel>(conn)
            .optional()
            .map_err(|e| DomainError::Database(e.to_string()))?
        {
            return Ok(existing.id);
        }

        let new_record = NewUnwrapBreadcrumbModel {
            hash: hash.to_string(),
            timestamp,
            category_id,
            type_id,
            level_id,
            data,
        };

        let id = diesel::insert_into(unwrap_breadcrumb::table)
            .values(&new_record)
            .returning(unwrap_breadcrumb::id)
            .get_result::<i32>(conn)
            .map_err(|e| DomainError::Database(e.to_string()))?;

        Ok(id)
    }
}
