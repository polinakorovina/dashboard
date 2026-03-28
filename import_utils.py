from data_pipeline import (
    load_single_file,
    load_and_prepare_two_dataframes,
    prepare_dashboard_data,
    read_dashboard_from_postgres,
    write_dashboard_to_postgres_append,
)


def process_uploaded_files(uploaded_files, postgres_url: str):
    if not uploaded_files or len(uploaded_files) != 2:
        raise ValueError("Нужно загрузить ровно 2 файла.")

    df_left = load_single_file(uploaded_files[0], uploaded_files[0].name)
    df_right = load_single_file(uploaded_files[1], uploaded_files[1].name)

    prepared_merge = load_and_prepare_two_dataframes(df_left, df_right)
    prepared_df = prepare_dashboard_data(prepared_merge)

    inserted_rows = write_dashboard_to_postgres_append(
        prepared_df,
        postgres_url=postgres_url,
    )

    db_df = read_dashboard_from_postgres(postgres_url)
    final_df = db_df if not db_df.empty else prepared_df

    return final_df, inserted_rows
